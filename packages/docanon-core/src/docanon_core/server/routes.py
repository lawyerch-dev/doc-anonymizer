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

from .. import __version__, convert, resources
from ..pipeline import Cancelled, prepare_detectors, process_file
from ..redaction.mapping import MappingStore
from . import downloads, llm_server, profiles, progress
from docanon_engine_ner_llm import LLMConfig

_MAX_BYTES = 50 * 1024 * 1024

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

# 前端是构建产物(Vite → apps/web/dist): / 发 index.html, 其余静态件都带哈希落在 /assets/ 下
_DIST_PREFIX = "/assets/"


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


def _apply_managed_llm(cfg) -> None:
    """选了目录里的模型 → 开跑前把服务弄就绪, 并用它的地址与别名。

    留空 `llm.model_id` 就走 `llm.base_url`/`llm.model`(自备服务, 高级) —— 这条路径一发都不碰。
    """
    if not cfg.detectors.get("llm_ner") or not cfg.llm_model_id:
        return
    info = llm_server.ensure(cfg.llm_model_id)
    cfg.llm.base_url = info["base_url"]
    cfg.llm.model = info["alias"]


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
            # _index() 走 resources.LAYOUT["web"], 现在指 apps/web/dist/index.html
            self._send(200, _index().read_bytes(), "text/html; charset=utf-8")
        elif p == "/health":
            # 带上 pid: 桌面壳用它确认"答话的是我自己拉起的那个后端", 而不是占着端口的旧孤儿
            # 带上 version: 界面底部显示的版本号取自这里 —— 只有一处真相(pyproject/__version__),
            # 前端不另存一份, 免得出现"界面写 v0.2.0、包是 v0.3.0"这种漂移
            self._json(200, {"ok": True, "pid": os.getpid(), "version": __version__})
        elif p == "/api/presets":
            self._json(200, {"presets": self._presets()})
        elif p == "/api/configs":
            self._json(200, {"configs": profiles.list_profiles(self.config_name)})
        elif p == "/api/models":
            try:
                llm_models = downloads.list_models()
            except downloads.DownloadError as exc:
                self._json(exc.code, {"error": str(exc)})
                return
            self._json(200, {
                "onnx_dirs": profiles.available_onnx_dirs(),
                "llm": {"base_url": LLMConfig.base_url, "model": LLMConfig.model},
                "llm_models": llm_models,
                "llm_server": llm_server.status(),
            })
        elif p == "/api/models/download":
            self._json(200, downloads.status())
        elif p.startswith("/api/progress/"):
            self._json(200, progress.state(p[len("/api/progress/"):]))
        elif p.startswith("/api/configs/"):
            self._get_config(p[len("/api/configs/"):])
        elif p.startswith(_DIST_PREFIX):
            self._serve_static(_web(), p.lstrip("/"))
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
        """解析 config: 缺省=启动配置; 字符串=内置/用户配置名; 字典=内联(改完即试跑)。

        返回 (config, name); 不可用时已发 400 并返回 (None, None)。
        """
        selected = payload.get("config")
        if selected is None:
            _apply_managed_llm(self.config)
            return self.config, self.config_name
        try:
            if isinstance(selected, dict):
                profiles.validate(selected)
                cfg = profiles.build_config(selected)
                name = "inline"
            elif isinstance(selected, str):
                cfg = profiles.build_config(profiles.load_profile(selected))
                name = selected
            else:
                raise profiles.ProfileError("config 只能是配置名或配置对象")
            _apply_managed_llm(cfg)  # 选了模型就先把它跑起来(起不来会抛, 见下)
            prepare_detectors(cfg)  # 少一层就报错: 缺模型/连不上在这里拦住
        except profiles.ProfileError as exc:
            self._json(400, {"error": f"配置不合法: {exc}"})
            return None, None
        except llm_server.LLMServerError as exc:
            # 缺 llama.cpp / 模型没下 / 起不来: 是"用不了", 不是"服务器崩了"
            self._json(exc.code, {"error": f"本地大模型起不来: {exc}"})
            return None, None
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"配置不可用: {exc}"})
            return None, None
        return cfg, name

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    # ---------- POST ----------
    def do_POST(self) -> None:  # noqa: N802
        p = self._path()
        try:
            payload = self._read_json()
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"请求解析失败: {exc}"})
            return
        if p == "/api/upload":
            self._upload(payload)
        elif p == "/api/anonymize":
            self._anonymize(payload)
        elif p == "/api/configs/import":
            self._import_config(payload)
        elif p == "/api/models/download":
            self._start_download(payload)
        elif p == "/api/models/download/cancel":
            self._json(200, downloads.cancel())
        elif p == "/api/anonymize/cancel":
            job = str(payload.get("job") or "")
            self._json(200, {"cancelled": progress.cancel(job)})
        else:
            self._send(404, b"not found", "text/plain")

    def _start_download(self, payload: dict) -> None:
        """只收目录里的 id —— 地址由目录拼, 不收 URL(否则就是个任意下载口)。"""
        model_id = payload.get("id")
        if not isinstance(model_id, str) or not model_id:
            self._json(400, {"error": "缺 id"})
            return
        try:
            state = downloads.start(model_id)
        except downloads.DownloadError as exc:
            self._json(exc.code, {"error": str(exc)})
            return
        self._json(202, state)

    # ---------- 配置写入 ----------
    def do_PUT(self) -> None:  # noqa: N802
        p = self._path()
        if not p.startswith("/api/configs/"):
            self._send(404, b"not found", "text/plain")
            return
        try:
            payload = self._read_json()
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"请求解析失败: {exc}"})
            return
        name = p[len("/api/configs/"):]
        try:
            profiles.save_profile(name, payload)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {"saved": True, "name": name})

    def do_DELETE(self) -> None:  # noqa: N802
        p = self._path()
        if not p.startswith("/api/configs/"):
            self._send(404, b"not found", "text/plain")
            return
        ref = p[len("/api/configs/"):]
        try:
            if profiles.is_builtin(ref):
                raise profiles.ProfileError(f"内置配置只读, 不能删除: {ref}")
            profiles.delete_profile(ref)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {"deleted": ref})

    def _import_config(self, payload: dict) -> None:
        try:
            text = base64.b64decode(payload["content_b64"]).decode("utf-8")
            name = profiles.import_yaml(Path(payload["filename"]).name, text)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"导入失败: {exc}"})
            return
        self._json(200, {"name": name})

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
        """入口: 先把 job 登记好再干活 —— "准备引擎"(起大模型/载 ONNX)那几秒也要能看见。"""
        job = payload.get("job")
        if job is None:
            self._anonymize_job(payload, None, None)
            return
        try:
            cancel = progress.begin(str(job))
        except progress.BadJobId as exc:
            self._json(400, {"error": str(exc)})
            return
        try:
            self._anonymize_job(payload, str(job), cancel)
        finally:
            progress.finish(str(job))

    def _anonymize_job(self, payload: dict, job: str | None, cancel) -> None:
        tick = None if job is None else (
            lambda stage, done=0, total=0: progress.update(job, stage, done, total)  # noqa: E731
        )
        if tick is not None:
            tick("prepare")   # 起本地大模型 / 加载 ONNX 都在这一段里, 别让它看起来像卡死
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
            res = process_file(src, work, cfg, store, progress=tick, cancel=cancel)
        except Cancelled:
            self._json(409, {"error": "已取消 —— 没有写任何产物"})
            return
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
