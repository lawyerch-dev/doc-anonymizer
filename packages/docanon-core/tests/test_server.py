"""Web 服务的对外契约与 sidecar 生命周期。

- `/health` 要报自己的 pid: 桌面壳拿它确认"答话的是我拉起的那个后端", 而不是占着端口的旧孤儿。
- 路径要 unquote: 浏览器把中文文件名按 %XX 发来(接口自己发的 `output_url` 就是中文路径)。
- 壳被 SIGKILL / 崩溃 / 走 Electrobun 自己的 SIGTERM quit 序列时, JS 侧的 child.kill()
  没有机会执行(实测过), 所以真正的兜底是 Python 侧的父进程监视。

真服务的起停见 `conftest.py` 的 `ephemeral_server`。
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

from docanon_core import server
from _soffice_stub import install_fake_soffice


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _upload_doc(base: str, tmp_path) -> dict:
    import base64

    return _post(base, "/api/upload", {
        "filename": "合同.doc",
        "content_b64": base64.b64encode(b"\xd0\xcf\x11\xe0 legacy").decode(),
    })


def _upload_text(base: str, text: str = "张三 13812340000\n") -> dict:
    import base64

    return _post(base, "/api/upload", {
        "filename": "note.txt",
        "content_b64": base64.b64encode(text.encode("utf-8")).decode(),
    })


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_parent_watch_is_off_unless_asked(monkeypatch):
    monkeypatch.delenv(server.ENV_EXIT_WITH_PARENT, raising=False)
    assert server._start_parent_watch() is False, "交互式 docanon web 不该被监视"
    assert not [t for t in threading.enumerate() if t.name == "parent-watch"]


def test_parent_watch_starts_when_enabled(monkeypatch):
    monkeypatch.setenv(server.ENV_EXIT_WITH_PARENT, "1")
    assert server._start_parent_watch() is True
    watchers = [t for t in threading.enumerate() if t.name == "parent-watch"]
    assert watchers, "开了开关却没起监视线程"
    assert watchers[0].daemon and watchers[0].is_alive()


def test_health_reports_its_own_pid(ephemeral_server):
    """壳靠这个 pid 判断答话的是不是自己拉起的后端(端口被旧孤儿占着时, 否则会开出一个假窗口)。"""
    with urllib.request.urlopen(f"{ephemeral_server}/health", timeout=5) as resp:
        body = json.loads(resp.read())
    assert body["ok"] is True
    assert body["pid"] == os.getpid()


def test_get_unquotes_percent_encoded_paths(tmp_path, ephemeral_server):
    """浏览器把中文文件名按 %XX 发来; 不 unquote 就 404 —— 中文上传件在预览/下载处打不开。

    接口发给前端的 `output_url` 就是原样带中文的路径, 所以这条是端到端契约。
    """
    name = "上传测试.txt"
    (tmp_path / "uploads" / "tok").mkdir(parents=True)
    (tmp_path / "uploads" / "tok" / name).write_text("hi", encoding="utf-8")

    with urllib.request.urlopen(f"{ephemeral_server}/uploads/tok/{quote(name)}", timeout=5) as resp:
        assert resp.status == 200
        assert resp.read().decode("utf-8") == "hi"


def test_sidecar_dies_when_its_parent_is_killed(tmp_path, repo_root):
    """真起一个"父进程"(sh)再杀掉它: 被 reparent 的 sidecar 必须自己了断。"""
    pid_file = tmp_path / "sidecar.pid"
    script = (
        "import os;"
        "from docanon_core.server import _watch_parent;"
        f"open({str(pid_file)!r}, 'w').write(str(os.getpid()));"
        "_watch_parent(os.getppid(), interval=0.2);"
    )
    # sh 退出后不该等后台任务; 前台等 pid 文件出现, 保证监视线程记下的是活着的父进程
    cmd = (
        f"{shlex.quote(sys.executable)} -c {shlex.quote(script)} & "
        f"while [ ! -f {shlex.quote(str(pid_file))} ]; do sleep 0.05; done"
    )
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    subprocess.run(["sh", "-c", cmd], env=env, timeout=30, check=True)

    pid = int(pid_file.read_text(encoding="utf-8"))
    assert _alive(pid), "sidecar 没起来, 测试本身有问题"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.1)
    if _alive(pid):
        os.kill(pid, 9)
        pytest.fail("父进程退出后 sidecar 仍在运行 —— 会孤儿化占住端口")


def test_anonymize_labels_legacy_conversion(tmp_path, monkeypatch, ephemeral_server):
    """Web 也必须把"产物已由 .doc 转换"讲出来, 不能静默换格式。"""
    install_fake_soffice(tmp_path, monkeypatch)
    up = _upload_doc(ephemeral_server, tmp_path)

    body = _post(ephemeral_server, "/api/anonymize", {"token": up["token"]})

    assert body["output_name"] == "合同.doc.redacted.docx"
    assert body["trace"]["converted_from"] == ".doc"


def test_anonymize_legacy_without_soffice_is_a_clear_error(tmp_path, monkeypatch, ephemeral_server):
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    up = _upload_doc(ephemeral_server, tmp_path)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"]})

    assert excinfo.value.code == 400, "缺 LibreOffice 是「用不了」, 不是服务器崩了(500)"
    assert "LibreOffice" in json.loads(excinfo.value.read())["error"]


def test_anonymize_legacy_when_disabled_is_a_clear_error(tmp_path, monkeypatch, ephemeral_server):
    from docanon_core.config import load_config

    cfg = load_config()
    cfg.legacy_convert = False
    monkeypatch.setattr(server.Handler, "config", cfg)
    up = _upload_doc(ephemeral_server, tmp_path)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"]})

    assert excinfo.value.code == 400, "开关关闭时也该是清晰的 4xx, 不是 500"
    assert "legacy_convert" in json.loads(excinfo.value.read())["error"]


def test_api_configs_lists_yaml_and_marks_current(ephemeral_server):
    with urllib.request.urlopen(ephemeral_server + "/api/configs", timeout=5) as resp:
        body = json.loads(resp.read())
    names = {c["name"] for c in body["configs"]}
    assert {"default.yaml", "onnx.yaml", "legal.yaml"} <= names
    current = [c["name"] for c in body["configs"] if c["current"]]
    assert current == ["default.yaml"]
    assert all(c.get("label") for c in body["configs"])


def test_anonymize_honours_a_named_config(ephemeral_server):
    up = _upload_text(ephemeral_server)

    body = _post(ephemeral_server, "/api/anonymize",
                 {"token": up["token"], "config": "default.yaml"})

    assert body["trace"]["config"] == "default.yaml"
    assert body["counts"].get("PHONE") == 1


def test_anonymize_rejects_a_bad_config_name(tmp_path, ephemeral_server):
    up = _upload_text(ephemeral_server)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize",
              {"token": up["token"], "config": "../default.yaml"})

    assert excinfo.value.code == 400
    assert "配置" in json.loads(excinfo.value.read())["error"]
