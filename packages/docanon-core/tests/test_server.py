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


def test_health_reports_version_from_the_single_source(ephemeral_server):
    """界面底部显示的版本号取自 /health —— 与包自己的版本必须同源, 否则迟早"界面 v0.2.0、包 v0.3.0"。"""
    from docanon_core import __version__

    with urllib.request.urlopen(f"{ephemeral_server}/health", timeout=5) as resp:
        body = json.loads(resp.read())
    assert body["version"] == __version__


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

    assert body["output_name"] == "【脱敏版】合同.doc.docx"
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
    # label 与 hint 都取自配置开头的注释: 前者是短名, 后者是"什么时候用它" —— 都是给用户看的,
    # 内置四套一个都不能缺(缺了界面就会露文件名给用户)。
    assert all(c.get("hint") for c in body["configs"]), "内置配置缺少'什么时候用'的说明"


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


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return json.loads(resp.read())


def test_api_configs_returns_kind_and_current(ephemeral_server):
    body = _get(ephemeral_server, "/api/configs")
    rows = {c["name"]: c for c in body["configs"]}
    assert rows["onnx.yaml"]["kind"] == "builtin"
    assert rows["default.yaml"]["current"] is True


def test_api_config_get_returns_editable_data(ephemeral_server):
    body = _get(ephemeral_server, "/api/configs/onnx.yaml")
    assert body["kind"] == "builtin"
    data = body["data"]
    assert data["strategies"]["PERSON"] == "redact"
    assert "model_dirs" in data["onnx"]


def test_api_config_get_unknown_is_404(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/nope.yaml")
    assert excinfo.value.code == 404


def test_api_config_get_traversal_is_rejected(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/..%2fdefault.yaml")
    assert excinfo.value.code in (400, 404)


def test_api_models_lists_onnx_dirs_and_llm_defaults(ephemeral_server):
    body = _get(ephemeral_server, "/api/models")
    assert isinstance(body["onnx_dirs"], list)
    assert body["llm"]["base_url"].startswith("http")
    assert body["llm_server"]["state"] in ("idle", "running", "error")


def test_managed_llm_overrides_endpoint_from_the_selected_model(monkeypatch):
    """选了目录里的模型 → 用托管服务的地址与别名, 而不是配置里那个"自备服务"的。"""
    from docanon_core.config import config_from_dict
    from docanon_core.server import routes

    cfg = config_from_dict({
        "detectors": {"llm_ner": True},
        "llm": {"model_id": "qwen3.8-4b-distill", "base_url": "http://127.0.0.1:8080/v1"},
    })
    monkeypatch.setattr(routes.llm_server, "ensure",
                        lambda mid: {"base_url": "http://127.0.0.1:8099/v1", "alias": mid})

    routes._apply_managed_llm(cfg)

    assert cfg.llm.base_url == "http://127.0.0.1:8099/v1"
    assert cfg.llm.model == "qwen3.8-4b-distill"


def test_managed_llm_is_skipped_without_a_model_id(monkeypatch):
    """留空 model_id = 用自备服务(高级): 一发都不碰。"""
    from docanon_core.config import config_from_dict
    from docanon_core.server import routes

    cfg = config_from_dict({"detectors": {"llm_ner": True}, "llm": {"model_id": ""}})
    monkeypatch.setattr(routes.llm_server, "ensure", lambda mid: pytest.fail("不该去起服务"))

    routes._apply_managed_llm(cfg)  # 不抛即通过


def test_anonymize_when_the_managed_llm_will_not_start_is_400(ephemeral_server, monkeypatch):
    """模型没装 / 没有 llama.cpp: 说清原因(400), 不是 500, 更不是静默少一层。"""
    from docanon_core.server import llm_server, routes

    up = _upload_text(ephemeral_server)
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["detectors"]["llm_ner"] = True
    inline["llm"]["model_id"] = "qwen3.8-4b-distill"

    def boom(_mid):
        raise llm_server.LLMServerError("「通用首选（4B 蒸馏）」还没安装 —— 先在设置里点「安装」")

    monkeypatch.setattr(routes.llm_server, "ensure", boom)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "config": inline})

    assert excinfo.value.code == 400
    assert "本地大模型起不来" in json.loads(excinfo.value.read())["error"]


def test_api_models_lists_downloadable_llm_models(ephemeral_server):
    """界面要拿这个名字/一句话/大小来渲染"选模型 + 下载", 所以字段一个都不能少。"""
    rows = _get(ephemeral_server, "/api/models")["llm_models"]
    assert {"qwen3.8-4b-distill", "qwen3.5-4b"} <= {r["id"] for r in rows}
    for r in rows:
        assert r["name"] and r["hint"], r["id"]
        assert r["size_gb"] > 0, r["id"]
        assert isinstance(r["downloaded"], bool), r["id"]
        # 文件名要给界面(用它当 llama-server 的模型名), 但不能给完整 URL —— 地址只由后端拼
        assert "/" not in r["file"], r["file"]


def test_download_status_starts_idle(ephemeral_server):
    assert _get(ephemeral_server, "/api/models/download")["state"] == "idle"


def test_download_unknown_id_is_400_not_a_download(ephemeral_server):
    """只收目录里的 id: 未知 id 必须当场拒绝, 不许变成"去下点别的"。"""
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/models/download", {"id": "nope"})
    assert excinfo.value.code == 400
    assert "id" in json.loads(excinfo.value.read())["error"]


def test_download_without_id_is_400(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/models/download", {})
    assert excinfo.value.code == 400


def test_model_catalog_is_not_offered_as_a_redaction_profile(ephemeral_server):
    """`configs/llm_models.yaml` 是资源不是"脱敏方案" —— 出现在 L1 下拉里就是噪音。"""
    names = {c["name"] for c in _get(ephemeral_server, "/api/configs")["configs"]}
    assert "llm_models.yaml" not in names
    assert {"default.yaml", "onnx.yaml", "legal.yaml"} <= names


def test_api_config_export_builtin_yaml(ephemeral_server):
    with urllib.request.urlopen(
        ephemeral_server + "/api/configs/onnx.yaml/export", timeout=5
    ) as resp:
        assert resp.status == 200
        assert "yaml" in resp.headers.get("Content-Type", "")
        assert "strategies" in resp.read().decode("utf-8")


def test_api_config_user_profile_roundtrip(tmp_path, ephemeral_server):
    d = tmp_path / "var" / "configs"
    d.mkdir(parents=True)
    (d / "mine.yaml").write_text(
        "strategies:\n  PERSON: redact\ndetectors:\n  rule: true\n", encoding="utf-8"
    )

    body = _get(ephemeral_server, "/api/configs/mine")
    assert body["kind"] == "user"
    assert body["data"]["strategies"]["PERSON"] == "redact"

    with urllib.request.urlopen(
        ephemeral_server + "/api/configs/mine/export", timeout=5
    ) as resp:
        assert resp.status == 200
        assert "PERSON: redact" in resp.read().decode("utf-8")


def _request(base, path, method, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def test_put_save_then_get_and_delete(tmp_path, ephemeral_server):
    data = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    data["strategies"]["PERSON"] = "pseudonym"

    assert _request(ephemeral_server, "/api/configs/mine", "PUT", data)["saved"] is True
    got = _get(ephemeral_server, "/api/configs/mine")["data"]
    assert got["strategies"]["PERSON"] == "pseudonym"

    _request(ephemeral_server, "/api/configs/mine", "DELETE")
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/mine")
    assert excinfo.value.code == 404


def test_put_rejects_bad_structure(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request(ephemeral_server, "/api/configs/mine", "PUT",
                 {"strategies": {"PERSON": "shred"}})
    assert excinfo.value.code == 400
    assert "未知策略值" in json.loads(excinfo.value.read())["error"]


def test_delete_builtin_is_rejected(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request(ephemeral_server, "/api/configs/default.yaml", "DELETE")
    assert excinfo.value.code == 400


def test_import_yaml_creates_user_profile(ephemeral_server):
    import base64
    text = "strategies:\n  ORG: redact\ndetectors:\n  rule: true\n"
    body = _post(ephemeral_server, "/api/configs/import", {
        "filename": "imported.yaml",
        "content_b64": base64.b64encode(text.encode()).decode(),
    })
    assert body["name"] == "imported"
    assert _get(ephemeral_server, "/api/configs/imported")["data"]["strategies"]["ORG"] == "redact"


def test_anonymize_with_inline_config_object(ephemeral_server):
    up = _upload_text(ephemeral_server, "张三 13812340000\n")
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["strategies"]["PHONE"] = "redact"

    body = _post(ephemeral_server, "/api/anonymize",
                 {"token": up["token"], "config": inline})

    assert body["trace"]["config"] == "inline"
    assert body["counts"].get("PHONE") == 1


def test_anonymize_inline_bad_strategy_is_400(ephemeral_server):
    up = _upload_text(ephemeral_server)
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["strategies"]["PHONE"] = "shred"

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "config": inline})
    assert excinfo.value.code == 400
    assert "未知策略值" in json.loads(excinfo.value.read())["error"]


def test_anonymize_inline_enabling_unavailable_onnx_is_400(ephemeral_server, monkeypatch):
    up = _upload_text(ephemeral_server)
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["detectors"]["onnx_ner"] = True
    inline["onnx"]["model_dirs"] = ["var/models/onnx/__nope__"]
    monkeypatch.setattr("docanon_core.server.routes.prepare_detectors",
                        lambda cfg: (_ for _ in ()).throw(RuntimeError("缺 ONNX 模型")))

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "config": inline})
    assert excinfo.value.code == 400
    assert "不可用" in json.loads(excinfo.value.read())["error"]


def test_root_serves_the_built_index(ephemeral_server):
    """`docanon web` 发的必须是构建产物(dist/index.html), 不是源码入口。"""
    with urllib.request.urlopen(ephemeral_server + "/", timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        html = resp.read().decode("utf-8")
    assert '<div id="root">' in html, "发出去的不是 Vite 构建后的 index"
    assert "/src/main.tsx" not in html, "发出去的是源码入口(未构建)"


def test_built_assets_are_served(ephemeral_server):
    """带哈希的 JS/CSS 落在 /assets/ 下, 必须能取到 —— 取不到就是白屏。"""
    from docanon_core import resources

    assets = sorted((resources.path("web") / "assets").glob("*.js"))
    assert assets, "构建产物里没有 assets/*.js, 先跑 npm run build:web"
    with urllib.request.urlopen(
        f"{ephemeral_server}/assets/{assets[0].name}", timeout=5
    ) as resp:
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type", "")


def test_bad_job_id_is_rejected(ephemeral_server):
    """job id 会被当字典键 —— 不能随便收(路径穿越 / 撑爆内存)。"""
    up = _upload_text(ephemeral_server)
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "job": "../evil"})
    assert excinfo.value.code == 400
    assert "job" in json.loads(excinfo.value.read())["error"]


def test_progress_is_readable_and_ends_at_done(ephemeral_server):
    """跑的时候进度读得到(前端就是靠它显示"识别第几段"), 跑完收尾成 done。"""
    up = _upload_text(ephemeral_server)

    body = _post(ephemeral_server, "/api/anonymize",
                 {"token": up["token"], "job": "job-abc123"})

    assert body["counts"].get("PHONE") == 1
    state = _get(ephemeral_server, "/api/progress/job-abc123")
    assert state["stage"] == "done"
    assert state["cancelled"] is False


def test_cancelled_run_is_409_not_a_broken_result(ephemeral_server, monkeypatch):
    """取消: 409 + 一句人话, 且**不产出任何文件**(半截产物比没产物更危险)。"""
    from docanon_core.pipeline import Cancelled
    from docanon_core.server import routes

    up = _upload_text(ephemeral_server)

    def cancelled_midway(*args, **kwargs):
        kwargs["progress"]("detect", 3, 9)          # 让进度停在半路
        raise Cancelled("已取消")

    monkeypatch.setattr(routes, "process_file", cancelled_midway)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize",
              {"token": up["token"], "job": "job-cancel1"})

    assert excinfo.value.code == 409
    assert "已取消" in json.loads(excinfo.value.read())["error"]
    assert _get(ephemeral_server, "/api/progress/job-cancel1")["stage"] == "done"


def test_cancel_endpoint_reports_whether_it_knew_the_job(ephemeral_server):
    assert _post(ephemeral_server, "/api/anonymize/cancel", {"job": "nobody"})["cancelled"] is False
