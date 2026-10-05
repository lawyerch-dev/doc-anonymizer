"""轻量 Web: 上传文件 → 脱敏 → 预览/下载。仅用标准库, 无额外依赖。

启动: docanon web --port 8000
"""
from __future__ import annotations

import argparse
import base64
import json
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import load_config
from ..mapping import MappingStore
from ..pipeline import process_file

_INDEX = Path(__file__).parent / "index.html"
_MAX_BYTES = 30 * 1024 * 1024  # 单文件 30MB 上限


class Handler(BaseHTTPRequestHandler):
    config = None  # 由 serve() 注入

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, _INDEX.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/health":
            self._json(200, {"ok": True})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/anonymize":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > _MAX_BYTES * 2:
            self._json(400, {"error": "文件为空或过大"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            name = Path(payload["filename"]).name
            raw = base64.b64decode(payload["content_b64"])
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"请求解析失败: {exc}"})
            return

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / name
            src.write_bytes(raw)
            out_dir = Path(td) / "out"
            out_dir.mkdir()
            store = MappingStore()
            try:
                res = process_file(src, out_dir, self.config, store)
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
                return
            out_path = Path(res.output_path)
            result: dict = {
                "counts": res.entity_counts,
                "output_name": out_path.name,
                "mapping": json.dumps(store.to_dict(), ensure_ascii=False),
            }
            data = out_path.read_bytes()
            if out_path.suffix.lower() == ".txt":
                result["kind"] = "text"
                result["text"] = data.decode("utf-8", errors="replace")
            else:
                result["kind"] = "image"
                result["image_b64"] = base64.b64encode(data).decode("ascii")
        self._json(200, result)

    def log_message(self, fmt: str, *args) -> None:  # 静默默认日志
        pass


def serve(port: int = 8000, config_path: str | None = None, open_browser: bool = True) -> None:
    Handler.config = load_config(config_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"doc-anonymizer Web 已启动: {url}  (Ctrl+C 退出)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="docanon-web")
    parser.add_argument("-p", "--port", type=int, default=8000)
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(args.port, args.config, not args.no_browser)


if __name__ == "__main__":
    main()
