"""HTTP 面: Handler 与它用到的路径/类型工具。

只负责"请求怎么被回答"; 服务怎么起、什么时候该自杀在 `lifecycle.py`, 编排在 `__init__.py`。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import tempfile
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

from .. import convert, resources
from ..config import load_config
from ..pipeline import prepare_detectors, process_file
from ..redaction.mapping import MappingStore
from . import profiles
from docanon_engine_ner_llm import LLMConfig

_MAX_BYTES = 50 * 1024 * 1024

# 运行期可选的配置(= configs/*.yaml): 前端下拉用, 换个口径不必重启。
# 缓存已加载(且预检过)的配置, 免得每个请求都重建检测器。
_CONFIG_CACHE: dict[str, object] = {}

# 资源位置都从 resources 取(调用者的 cwd 与安装布局都无关), 所以用函数而不是导入期常量
def _web() -> Path:
    return resources.path("web")


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

# 前端自己的静态件(app.css / app.js): 零构建, 直接由本服务发出去
_WEB_ASSETS = {"/app.css": "app.css", "/app.js": "app.js"}


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
    config_name = None
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

    def _path(self) -> str:
        """请求路径(去掉 query)。

        必须 unquote: 浏览器会把中文等非 ASCII 文件名按 %XX 编码送来, BaseHTTPRequestHandler
        给的 `self.path` 是原样的百分号串 —— 不还原就找不到文件, 中文上传件在预览/下载处一律 404。
        """
        return unquote(self.path.split("?", 1)[0])

    # ---------- GET ----------
    def do_GET(self) -> None:  # noqa: N802
        p = self._path()
        if p in ("/", "/index.html"):
            self._send(200, _index().read_bytes(), "text/html; charset=utf-8")
        elif p == "/health":
            # 带上 pid: 桌面壳用它确认"答话的是我自己拉起的那个后端", 而不是占着端口的旧孤儿
            self._json(200, {"ok": True, "pid": os.getpid()})
        elif p == "/api/presets":
            self._json(200, {"presets": self._presets()})
        elif p == "/api/configs":
            self._json(200, {"configs": profiles.list_profiles(self.config_name)})
        elif p == "/api/models":
            self._json(200, {
                "onnx_dirs": profiles.available_onnx_dirs(),
                "llm": {"base_url": LLMConfig.base_url, "model": LLMConfig.model},
            })
        elif p.startswith("/api/configs/"):
            self._get_config(p[len("/api/configs/"):])
        elif p in _WEB_ASSETS:
            self._send_file(_web() / _WEB_ASSETS[p])
        elif p.startswith("/samples/"):
            self._serve_static(_samples(), p[len("/samples/"):])
        elif p.startswith("/file-viewer/"):
            self._serve_static(_vendor(), p[len("/file-viewer/"):])
        elif p.startswith("/uploads/") or p.startswith("/outputs/"):
            self._serve_static(self.out_root, p[1:])
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_static(self, base: Path, rel: str) -> None:
        f = _safe_join(base, rel)
        self._send_file(f) if f else self._send(404, b"bad path", "text/plain")

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

    # ---------- 配置只读 ----------
    def _get_config(self, ref: str) -> None:
        if ref.endswith("/export"):
            try:
                text = profiles.export_yaml(ref[: -len("/export")])
            except profiles.ProfileError as exc:
                self._json(404, {"error": str(exc)})
                return
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-yaml; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{Path(ref[:-len("/export")]).stem}.yaml"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            data = profiles.load_profile(ref)
        except profiles.ProfileError as exc:
            code = 404 if "不存在" in str(exc) else 400
            self._json(code, {"error": str(exc)})
            return
        self._json(200, {"ref": ref, "kind": "builtin" if profiles.is_builtin(ref) else "user", "data": data})

    def _resolve_config(self, payload: dict):
        """按请求里的 config 名选一份配置并预检; 无名字用启动配置。

        返回 (config, name); 名字非法/配置不可用时已发 400 并返回 (None, None)。
        """
        name = payload.get("config")
        if not name:
            return self.config, self.config_name
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".yaml"):
            self._json(400, {"error": f"非法配置名: {name!r}"})
            return None, None
        path = resources.config_path(name)
        if not path.is_file():
            self._json(400, {"error": f"配置不存在: {name}"})
            return None, None
        cfg = _CONFIG_CACHE.get(name)
        if cfg is None:
            try:
                cfg = load_config(path)
                prepare_detectors(cfg)  # 少一层就报错: 缺模型/起不来在这里拦住
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": f"配置 {name} 不可用: {exc}"})
                return None, None
            _CONFIG_CACHE[name] = cfg
        return cfg, name

    # ---------- POST ----------
    def do_POST(self) -> None:  # noqa: N802
        p = self._path()
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
        cfg, cfg_name = self._resolve_config(payload)
        if cfg is None:
            return
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

        # 旧格式要先转: 缺 LibreOffice 是"用不了"(400 + 可操作原因), 不是服务器崩了
        if src.suffix.lower() in convert.LEGACY_EXTENSIONS:
            if not cfg.legacy_convert:
                self._json(400, {
                    "error": f"旧格式转换已关闭(legacy_convert=false): 不支持 {src.suffix}",
                })
                return
            reason = convert.unavailable_reason()
            if reason:
                self._json(400, {"error": reason})
                return

        token = uuid.uuid4().hex[:12]
        work = self.out_root / "outputs" / token
        work.mkdir(parents=True, exist_ok=True)
        store = MappingStore()
        try:
            res = process_file(src, work, cfg, store)
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
                "converted_from": res.converted_from,
                "config": cfg_name,
                "detectors": res.detectors,
                "timing": res.timing,
                "detections": res.detections,
            },
        })

    def log_message(self, fmt: str, *args) -> None:  # 静默默认日志
        pass
