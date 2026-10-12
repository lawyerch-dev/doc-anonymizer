"""HTTP 面: Handler 与它用到的路径/类型工具。

只负责"请求怎么被回答"; 服务怎么起、什么时候该自杀在 `lifecycle.py`, 编排在 `__init__.py`。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import tempfile
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote, unquote

from .. import __version__, convert, resources
from ..pipeline import Cancelled, prepare_detectors, process_file
from ..redaction.mapping import MappingStore
from . import downloads, llm_server, prepare, profiles, progress, settings
from docanon_engine_ner_llm import LLMConfig

_MAX_BYTES = 50 * 1024 * 1024

# 一批的上限: 界面"选文件夹"时前端先拦一道(给出人话), 这里是后端的硬底线(直接调 API 也拦得住)
BATCH_MAX_FILES = 300
BATCH_MAX_BYTES = 500 * 1024 * 1024


# 这些目录里是构建/供应商产物(文件名带哈希或钉住版本), 内容变了名字就变 —— 可以放心长缓存
_IMMUTABLE_DIRS = {"assets", "file-viewer"}


def _cache_control(path: Path) -> str:
    """静态件的缓存策略。

    **入口 HTML 绝不能缓存**: 它引用的是带哈希的产物, 一旦浏览器缓存住旧的那份,
    改完前端刷新页面看到的还是旧界面(踩过: 用户反复刷新仍看到旧版, 以为是没改)。
    带哈希的资源反过来缓存一年都不怕 —— 内容变了文件名就变。
    """
    if _IMMUTABLE_DIRS & set(path.parts):
        return "public, max-age=31536000, immutable"
    return "no-cache"


def supported_extensions() -> list[str]:
    """界面上"选文件夹"预过滤用的扩展名清单。

    **不另抄一份**: 直接问抽取器注册表 —— 加个抽取器就自动出现在界面上。
    旧格式(.doc/.xls)也算在内: 它们到底能不能跑取决于配置与 LibreOffice, 那是运行时的三态该说的,
    预过滤阶段把它当"不支持"会让用户连点都不会点。
    """
    from ..extractors.base import extractor_classes

    return sorted({ext for cls in extractor_classes() for ext in cls.extensions})


def _batch_files(root: Path) -> list[tuple[Path, Path]]:
    """批次目录里的 (绝对路径, 相对路径), 按相对路径排序。

    跳过隐藏项(`.` 开头的任何一层) —— 与 CLI `_collect` 同一套规则: 否则每个 Mac 文件夹都会
    多出一堆 `.DS_Store` 进"不支持"。隐藏项不算 unsupported, 由调用方单独说"已忽略 N 个"。
    """
    return [
        (p, p.relative_to(root))
        for p in sorted(root.rglob("*"))
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
    ]


def _make_zip(out_dir: Path, dest: Path) -> int:
    """把产物目录打成一个 zip, **不含 `mapping.json`** —— 它含原文, 是与脱敏件分开外发的东西。"""
    import zipfile

    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out_dir.rglob("*")):
            if path.is_file() and path.name != "mapping.json":
                zf.write(path, path.relative_to(out_dir))
                count += 1
    return count

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
    # 显式写死: mimetypes 在 Windows 上会读注册表, 同一份代码不该因机器而变
    ".zip": "application/zip",
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
    def _send(self, code: int, body: bytes, ctype: str, cache: str | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        self._send(200, path.read_bytes(), _ctype(path), cache=_cache_control(path))

    def _send_download(self, path: Path, filename: str) -> None:
        """带 Content-Disposition 的下载, **边读边发**。

        整包可能有几百 MB, 不能像 `_send_file` 那样整份读进内存; 文件名按 RFC 5987 编码 ——
        中文名不编码会乱码或被截成 "download.zip"。
        """
        if not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        self.send_response(200)
        self.send_header("Content-Type", _ctype(path))
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
        self.end_headers()
        with path.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile, 1 << 16)

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
            # _index() 走 resources.LAYOUT["web"], 现在指 apps/web/dist/index.html。
            # 走 _send_file 是为了带上缓存头: 入口 HTML 必须 no-cache(见 _cache_control)
            self._send_file(_index())
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
        elif p == "/api/formats":
            self._json(200, {"extensions": supported_extensions()})
        elif p == "/api/settings":
            # 界面偏好(收件规则这类): 从没改过就是 {}, 由界面用自己的默认值(默认值只有前端一处真相)
            try:
                self._json(200, settings.load())
            except settings.SettingsError as exc:
                self._json(400, {"error": str(exc)})
        elif p == "/api/models/download":
            self._json(200, downloads.status())
        elif p == "/api/prepare":
            self._json(200, prepare.status())
        elif p.startswith("/api/progress/"):
            self._json(200, progress.state(p[len("/api/progress/"):]))
        elif p.startswith("/api/batch/"):
            self._get_batch_zip(p[len("/api/batch/"):])
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

    def _get_batch_zip(self, rest: str) -> None:
        """`/api/batch/<产物目录>/zip?name=<文件夹名>` → 整包下载。

        产物目录名来自服务端自己发的 `zip_url`, 但仍要过 `_safe_join`: 这个端点接受外部输入。
        """
        out_token, _, kind = rest.partition("/")
        if kind != "zip":
            self._json(404, {"error": "not found"})
            return
        out = _safe_join(self.out_root / "outputs", out_token)
        if out is None or not out.is_dir():
            self._json(404, {"error": "批次产物不存在"})
            return
        name = "脱敏产物"
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        for part in query.split("&"):
            if part.startswith("name="):
                name = Path(unquote(part[len("name="):])).name or name
        tmp = self.out_root / f"zip-{uuid.uuid4().hex[:8]}.zip"
        try:
            _make_zip(out, tmp)
            self._send_download(tmp, f"【脱敏版】{name}.zip")
        finally:
            tmp.unlink(missing_ok=True)

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

    def _resolve_config_raw(self, payload: dict):
        """只解析配置, **不做引擎预检、不起大模型** —— 首次"初始化"要在引擎就绪之前先跑。

        返回 (config, name); 配置不可用时已发 400 并返回 (None, None)。
        """
        selected = payload.get("config")
        if selected is None:
            return self.config, self.config_name
        try:
            if isinstance(selected, dict):
                profiles.validate(selected)
                return profiles.build_config(selected), "inline"
            if isinstance(selected, str):
                return profiles.build_config(profiles.load_profile(selected)), selected
            raise profiles.ProfileError("config 只能是配置名或配置对象")
        except profiles.ProfileError as exc:
            self._json(400, {"error": f"配置不合法: {exc}"})
            return None, None
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"配置不可用: {exc}"})
            return None, None

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
        elif p == "/api/prepare":
            self._start_prepare(payload)
        elif p == "/api/prepare/cancel":
            self._json(200, prepare.cancel())
        elif p == "/api/models/download/cancel":
            self._json(200, downloads.cancel())
        elif p == "/api/anonymize/cancel":
            job = str(payload.get("job") or "")
            self._json(200, {"cancelled": progress.cancel(job)})
        else:
            self._send(404, b"not found", "text/plain")

    def _start_prepare(self, payload: dict) -> None:
        """首次"初始化": 按方案把缺的识别模型补上。

        不做引擎预检 —— 预检会因"模型还没下"而报错, 那正是这次要解决的事。补完再预检,
        由跑脱敏那一步负责(少一层照样报错)。
        """
        cfg, _name = self._resolve_config_raw(payload)
        if cfg is None:
            return
        try:
            self._json(200, prepare.start(cfg))
        except prepare.PrepareError as exc:
            self._json(exc.code, {"error": str(exc)})

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
        if p == "/api/settings":
            try:
                payload = self._read_json()
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": f"请求解析失败: {exc}"})
                return
            try:
                self._json(200, {"saved": True, "settings": settings.save(payload)})
            except settings.SettingsError as exc:
                self._json(400, {"error": str(exc)})
            return
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
        batch = payload.get("batch")
        if batch:
            # 批次(选文件夹): 一个文件夹里的多份进同一个目录, 保留相对层级
            if not progress.NAME_RE.match(str(batch)):
                self._json(400, {"error": "非法批次 id"})
                return
            rel = str(payload.get("relpath") or name).replace("\\", "/")
            dest = _safe_join(self.out_root / "uploads" / str(batch), rel)
            if dest is None:
                self._json(400, {"error": f"非法相对路径: {rel}"})
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            token, shown = str(batch), rel
        else:
            token = uuid.uuid4().hex[:12]
            dest = self.out_root / "uploads" / token / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            shown = name
        self._json(200, {"token": token, "filename": shown, "url": f"/uploads/{token}/{shown}"})

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
        # 批次(选文件夹): 一个文件夹一次跑完, 每份是独立的原子单位(见 _anonymize_batch)
        if payload.get("batch"):
            self._anonymize_batch(str(payload["batch"]), cfg, job, cancel)
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

    def _anonymize_batch(self, batch: str, cfg, job: str | None, cancel) -> None:
        """一个文件夹一次跑完。

        每份都是**独立的原子单位**: `process_file` 自带"先写 .tmp 再 replace", 所以取消或中途失败时
        已经跑完的那几份产物是完整的、账本也记着 —— 这不是"半成品", 与单份取消(整份不落产物)不冲突。

        逐份三态与 CLI 的 `run` 一致: 不支持的记 `unsupported` 带原因, 出错的记 `error`,
        **绝不静默少一份**。
        """
        if not progress.NAME_RE.match(batch):
            self._json(400, {"error": "非法批次 id"})
            return
        src_root = self.out_root / "uploads" / batch
        pairs = _batch_files(src_root) if src_root.is_dir() else []
        if not pairs:
            self._json(400, {"error": "这个文件夹里没有可脱敏的文档"})
            return
        if len(pairs) > BATCH_MAX_FILES:
            self._json(400, {
                "error": f"一次最多 {BATCH_MAX_FILES} 份(这次 {len(pairs)} 份), 分两批跑",
            })
            return
        if sum(p.stat().st_size for p, _ in pairs) > BATCH_MAX_BYTES:
            self._json(400, {"error": "整批超过 500MB, 分两批跑"})
            return

        # 旧格式要先转: 缺 LibreOffice 时整批记 unsupported(带原因), 而不是炸成 error(与 CLI 同法)
        legacy_blocked = None
        if any(p.suffix.lower() in convert.LEGACY_EXTENSIONS for p, _ in pairs):
            legacy_blocked = convert.unavailable_reason()

        token = uuid.uuid4().hex[:12]
        work = self.out_root / "outputs" / token
        work.mkdir(parents=True, exist_ok=True)
        store = MappingStore()
        results: list[dict] = []
        total = len(pairs)
        cancelled = False

        for i, (src, rel) in enumerate(pairs, start=1):
            rel_s = str(rel).replace(os.sep, "/")
            if job is not None:
                progress.update(job, "extract", 0, 0, file=rel_s, index=i, total_files=total)
            if legacy_blocked and src.suffix.lower() in convert.LEGACY_EXTENSIONS:
                results.append({"source": rel_s, "status": "unsupported", "reason": legacy_blocked})
                continue

            def tick(stage: str, done: int = 0, tot: int = 0, _rel=rel_s, _i=i) -> None:
                if job is not None:
                    progress.update(job, stage, done, tot, file=_rel, index=_i, total_files=total)

            try:
                res = process_file(src, work, cfg, store, rel=rel, progress=tick, cancel=cancel)
            except Cancelled:
                cancelled = True
                break
            except ValueError as exc:  # build_extractor: 不支持的类型
                results.append({"source": rel_s, "status": "unsupported", "reason": str(exc)})
                continue
            except Exception as exc:  # noqa: BLE001
                results.append({"source": rel_s, "status": "error", "reason": str(exc)})
                continue
            # output_path 是 str(单份流程也是 `Path(res.output_path).name` 这么用的)
            out_path = Path(res.output_path)
            out_rel = str(out_path.relative_to(work) if out_path.is_absolute() else out_path)
            results.append({
                "source": rel_s,
                "status": "ok",
                "output_name": out_path.name,
                "output_url": f"/outputs/{token}/{out_rel.replace(os.sep, '/')}",
                "counts": res.entity_counts,
            })

        # 取消也要落账本: 已完成的部分不能白跑(否则那些产物再也拼不回原文)
        store.save(work / "mapping.json")
        self._json(200, {
            "batch": {"cancelled": cancelled, "total": total},
            "summary": {
                "total": total,
                "ok": sum(1 for r in results if r["status"] == "ok"),
                "unsupported": sum(1 for r in results if r["status"] == "unsupported"),
                "error": sum(1 for r in results if r["status"] == "error"),
            },
            "results": results,
            "mapping_url": f"/outputs/{token}/mapping.json",
            "zip_url": f"/api/batch/{token}/zip",
        })

    def log_message(self, fmt: str, *args) -> None:  # 静默默认日志
        pass
