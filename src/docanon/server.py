"""轻量 Web: 选文档(预设/上传) → file-viewer 预览 → 脱敏 → 原格式前后对比。

仅标准库; 预览资源来自 vendor/file-viewer(file-viewer 预构建包)。
启动: docanon web --port 8000
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import mimetypes
import sys
import tempfile
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import resources
from .config import load_config
from .mapping import MappingStore
from .pipeline import prepare_detectors, process_file

_MAX_BYTES = 50 * 1024 * 1024


# 资源位置都从 resources 取(调用者的 cwd 与安装布局都无关), 所以用函数而不是导入期常量
def _index() -> Path:
    return resources.web_index()


def _vendor() -> Path:
    return resources.vendor_dir()


def _samples() -> Path:
    return resources.samples_dir()

_CTYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".wasm": "application/wasm",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".css": "text/css",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
}

_PREVIEWABLE = {".docx", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv"}


def _ctype(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in _CTYPES:
        return _CTYPES[suf]
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


def _safe_join(base: Path, rel: str) -> Path | None:
    try:
        target = (base / rel).resolve()
    except (OSError, ValueError):
        return None
    if base.resolve() in target.parents or target == base.resolve():
        return target
    return None


class Handler(BaseHTTPRequestHandler):
    config = None
    out_root = Path(tempfile.mkdtemp(prefix="docanon-web-"))

    # ---------- 响应工具 ----------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, path.read_bytes(), _ctype(path))

    # ---------- GET ----------
    def do_GET(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        if p in ("/", "/index.html"):
            self._send(200, _index().read_bytes(), "text/html; charset=utf-8")
        elif p == "/health":
            self._json(200, {"ok": True})
        elif p == "/api/presets":
            self._json(200, {"presets": self._presets()})
        elif p.startswith("/samples/"):
            f = _safe_join(_samples(), p[len("/samples/"):])
            self._send_file(f) if f else self._send(404, b"bad path", "text/plain")
        elif p.startswith("/file-viewer/"):
            f = _safe_join(_vendor(), p[len("/file-viewer/"):])
            self._send_file(f) if f else self._send(404, b"bad path", "text/plain")
        elif p.startswith("/uploads/") or p.startswith("/outputs/"):
            f = _safe_join(self.out_root, p[1:])
            self._send_file(f) if f else self._send(404, b"bad path", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    @staticmethod
    def _presets() -> list[dict]:
        if not _samples().is_dir():
            return []
        out = []
        for f in sorted(_samples().iterdir()):
            if f.suffix.lower() in _PREVIEWABLE:
                out.append({
                    "name": f.name,
                    "url": f"/samples/{f.name}",
                    "size": f.stat().st_size,
                    "preview": True,
                })
        return out

    # ---------- POST ----------
    def do_POST(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"请求解析失败: {exc}"})
            return
        if p == "/api/upload":
            self._upload(payload)
        elif p == "/api/anonymize":
            self._anonymize(payload)
        else:
            self._send(404, b"not found", "text/plain")

    def _upload(self, payload: dict) -> None:
        try:
            name = Path(payload["filename"]).name
            raw = base64.b64decode(payload["content_b64"])
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"上传失败: {exc}"})
            return
        if len(raw) > _MAX_BYTES:
            self._json(400, {"error": "文件过大(>50MB)"})
            return
        token = uuid.uuid4().hex[:12]
        dest = self.out_root / "uploads" / token
        dest.mkdir(parents=True, exist_ok=True)
        (dest / name).write_bytes(raw)
        self._json(200, {"token": token, "filename": name, "url": f"/uploads/{token}/{name}"})

    def _anonymize(self, payload: dict) -> None:
        # 输入来源: 预设文件名 或 已上传 token
        if payload.get("preset"):
            src = _samples() / Path(payload["preset"]).name
            if not src.is_file():
                self._json(404, {"error": "预设不存在"})
                return
        elif payload.get("token"):
            up = self.out_root / "uploads" / payload["token"]
            files = list(up.glob("*")) if up.is_dir() else []
            if not files:
                self._json(404, {"error": "上传不存在"})
                return
            src = files[0]
        else:
            self._json(400, {"error": "缺少 preset 或 token"})
            return

        token = uuid.uuid4().hex[:12]
        work = self.out_root / "outputs" / token
        work.mkdir(parents=True, exist_ok=True)
        store = MappingStore()
        try:
            res = process_file(src, work, self.config, store)
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": str(exc)})
            return
        store.save(work / "mapping.json")
        out_name = Path(res.output_path).name
        self._json(200, {
            "output_name": out_name,
            "output_url": f"/outputs/{token}/{out_name}",
            "counts": res.entity_counts,
            "kind": Path(out_name).suffix.lower().lstrip("."),
            "trace": {
                "source": src.name,
                "extractor": res.extractor,
                "detectors": res.detectors,
                "timing": res.timing,
                "detections": res.detections,
            },
        })

    def log_message(self, fmt: str, *args) -> None:  # 静默默认日志
        pass


def serve(port: int = 8000, config_path: str | None = None, open_browser: bool = True) -> None:
    try:
        Handler.config = load_config(config_path)
        # 预检: 引擎没准备好就别说"打开窗口点一下就知道失败了"
        prepare_detectors(Handler.config)
    except Exception as exc:  # noqa: BLE001
        print(f"Web 未启动: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="docanon-web")
    parser.add_argument("-p", "--port", type=int, default=8000)
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(args.port, args.config, not args.no_browser)


if __name__ == "__main__":
    main()
