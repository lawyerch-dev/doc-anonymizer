"""托管 llama-server: 选了模型就自动用它 —— 起服务不再甩给用户。

**不真起 llama-server**(模型几个 G): 这里覆盖"该不该起、复用还是换掉、起不来怎么说"这几条判断,
以及一条底线: 起不来必须抛错(带原因), 绝不静默少一层(见 `05-security.md`)。
"""
from __future__ import annotations

import pytest

from docanon_core.server import downloads, llm_server

MODEL = "qwen3.8-4b-distill"


@pytest.fixture(autouse=True)
def _clean_singleton(monkeypatch):
    """每个用例都从"没有托管进程"开始, 结束后也不留全局状态。"""
    for name, value in (("_child", None), ("_child_model", ""), ("_child_port", 0), ("_child_error", "")):
        monkeypatch.setattr(llm_server, name, value)
    yield
    llm_server._child = None
    llm_server._child_model = ""
    llm_server._child_port = 0
    llm_server._child_error = ""


def test_unknown_model_id_is_rejected():
    with pytest.raises(downloads.DownloadError):
        llm_server.ensure("nope")


def test_not_installed_is_a_clear_error(monkeypatch):
    """没下模型时说的话必须能照做: 去点「安装」, 而不是一个连不上的地址。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: False)
    with pytest.raises(llm_server.LLMServerError) as excinfo:
        llm_server.ensure(MODEL)
    assert "安装" in str(excinfo.value)
    assert excinfo.value.code == 400


def test_missing_binary_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: True)
    monkeypatch.setattr(llm_server, "_probe", lambda *a, **k: None)
    monkeypatch.setattr(llm_server.shutil, "which", lambda _name: None)
    with pytest.raises(llm_server.LLMServerError) as excinfo:
        llm_server.ensure(MODEL)
    assert "llama.cpp" in str(excinfo.value)
    assert excinfo.value.code == 500


def test_reuses_a_server_already_serving_that_alias(monkeypatch):
    """端口上正好是我们要的模型(例如上一次没退干净的孤儿) → 复用, 别再吃一份 3G 内存。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: True)
    monkeypatch.setattr(llm_server, "_probe", lambda port, timeout=2.0: [MODEL])
    monkeypatch.setattr(llm_server, "_spawn_locked", lambda *a: pytest.fail("不该起新进程"))

    info = llm_server.ensure(MODEL)

    assert info["alias"] == MODEL
    assert info["base_url"] == f"http://127.0.0.1:{llm_server.DEFAULT_PORT}/v1"
    assert info["pid"] is None, "复用的不是我们的进程, 不该记成自己的"
    assert llm_server.status()["state"] == "running"


def test_switching_model_spawns_a_new_one(monkeypatch):
    """端口上是别的模型 → 不能被它糊弄过去, 得按选中的模型另起一个。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: True)
    monkeypatch.setattr(llm_server, "_probe", lambda port, timeout=2.0: ["qwen3.5-4b"])
    monkeypatch.setattr(llm_server.shutil, "which", lambda _n: "/use/less/llama-server")
    monkeypatch.setattr(llm_server, "_free_port", lambda start, tries=20: 8099)
    spawned: dict = {}

    def fake_spawn(binary, path, model_id, port):
        spawned.update(model_id=model_id, port=port, file=path.name)
        llm_server._child_model = model_id
        llm_server._child_port = port

    monkeypatch.setattr(llm_server, "_spawn_locked", fake_spawn)

    info = llm_server.ensure(MODEL)

    assert spawned["model_id"] == MODEL
    assert spawned["port"] == 8099
    assert spawned["file"] == "Qwen3.8-4B-Q4_K_M.gguf"
    assert info["base_url"] == "http://127.0.0.1:8099/v1"


def test_boot_failure_reports_a_reason(monkeypatch):
    """进程启动即退出 → 报错带原因(不能"点了没反应")。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: True)
    monkeypatch.setattr(llm_server, "_probe", lambda *a, **k: None)
    monkeypatch.setattr(llm_server.shutil, "which", lambda _n: "/use/less/llama-server")

    class DeadProc:
        pid = 4242
        stderr = iter(["llama-server: failed to load model\n"])

        def poll(self):
            return 1

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 1

        def kill(self):
            return None

    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda *a, **k: DeadProc())

    with pytest.raises(llm_server.LLMServerError) as excinfo:
        llm_server.ensure(MODEL)
    assert "启动即退出" in str(excinfo.value)
    assert excinfo.value.code == 500


def test_idle_status_is_not_an_error():
    """没起过服务时是 idle —— 界面据此显示"没在跑", 不是"失败"。"""
    assert llm_server.status() == {"state": "idle", "model_id": "", "port": 0, "error": ""}


def test_stop_forgets_the_reused_server(monkeypatch):
    """stop 只收拾我们碰过的状态: 复用的服务不是我们起的, 不该去杀它。"""
    killed: list = []

    class AliveProc:
        pid = 777

        def poll(self):
            return None

        def terminate(self):
            killed.append(self.pid)

        def wait(self, timeout=None):
            return 0

    llm_server._child = AliveProc()
    llm_server._child_model = MODEL
    llm_server._child_port = 8090

    llm_server.stop()

    assert killed == [777], "自己起的那个要收掉"
    assert llm_server.status()["state"] == "idle"
