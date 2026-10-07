"""共享 fixture: "测试怎么找仓库根 / 怎么起一个真服务"只留一种写法。

样板原本散在每个测试文件里(各自算 `REPO_ROOT`、各自 `ThreadingHTTPServer`、各自塞 PYTHONPATH),
加一个测试就要再抄一遍; 收敛到这里, 也让"测试跑在什么根上"这件事只有一个答案。
"""
from __future__ import annotations

import pathlib
import threading
from http.server import ThreadingHTTPServer
from typing import Iterator

import pytest

from docanon import server

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """仓库根(也是资源根): 需要断言"文件在不在/相对路径对不对"的测试用它。"""
    return REPO_ROOT


@pytest.fixture
def ephemeral_server(tmp_path, monkeypatch) -> Iterator[str]:
    """起一个真的 HTTP 服务(随机端口, 用完即关), 返回 base URL。

    服务的 `out_root` 指向 tmp_path, 所以测试要把上传件/产物放进 `tmp_path/uploads/...`
    或 `tmp_path/outputs/...` 就能被访问到。
    """
    monkeypatch.setattr(server.Handler, "out_root", tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
