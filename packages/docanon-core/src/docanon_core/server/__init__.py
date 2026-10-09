"""轻量 Web: 选文档(预设/上传) → file-viewer 预览 → 脱敏 → 原格式前后对比。

仅标准库; 预览资源来自 var/vendor/file-viewer(file-viewer 预构建包)。
启动: docanon web --port 8000

拆成三块: `routes.py`(怎么答请求) / `lifecycle.py`(什么时候该自杀) / 本文件(怎么起服务)。
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from ..config import load_config
from ..pipeline import prepare_detectors
from . import llm_server
from .lifecycle import ENV_EXIT_WITH_PARENT, _start_parent_watch, _watch_parent
from .routes import Handler, _apply_managed_llm, _index, _vendor

__all__ = [
    "Handler",
    "ENV_EXIT_WITH_PARENT",
    "serve",
    "main",
    "_start_parent_watch",
    "_watch_parent",
]


def serve(port: int = 8000, config_path: str | None = None, open_browser: bool = True) -> None:
    # 前端页面是资源根下的静态文件: 先确认它在, 否则起个只能返回 404 的服务等于骗人
    if not _index().is_file():
        print(
            f"Web 未启动: 缺前端页面 {_index()}(资源根解析错了? 可用 DOCANON_ROOT 指定)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        Handler.config = load_config(config_path)
        Handler.config_name = Path(config_path).name if config_path else "default.yaml"
        # 启动配置里已经选了模型(-c llm.yaml) → 先把服务起好, 否则下面这关一定过不去
        _apply_managed_llm(Handler.config)
        # 预检: 引擎没准备好就别说"打开窗口点一下就知道失败了"
        prepare_detectors(Handler.config)
    except Exception as exc:  # noqa: BLE001
        llm_server.stop()
        print(f"Web 未启动: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    _start_parent_watch()
    if not _vendor().is_dir():
        print(
            f"警告: 缺预览资源 {_vendor()} —— 页面能开但预览区全空白。"
            "先跑 ./scripts/fetch_file_viewer.sh",
            file=sys.stderr,
        )
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"doc-anonymizer Web: {url}  (Ctrl+C 退出)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
        llm_server.stop()  # 我们起的那个大模型服务跟着一起收


def main() -> None:
    parser = argparse.ArgumentParser(prog="docanon-web")
    parser.add_argument("-p", "--port", type=int, default=8000)
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(args.port, args.config, not args.no_browser)


if __name__ == "__main__":
    main()
