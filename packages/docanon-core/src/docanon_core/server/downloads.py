"""界面内的大模型下载: 目录 → 后台任务 → 进度 / 取消。

只管"下载一个 gguf"这件事: 读目录、拼地址、Range 续传、原子落盘、进度状态。
HTTP 那段在 `routes.py`, 这里不认识 BaseHTTPRequestHandler。

**只收目录里的 id, 不收 URL**: 下载地址一律由 `configs/llm_models.yaml` 的 `repo` + `file` 拼出。
接口若接受任意 URL, 这个功能就成了"任意下载 / SSRF"的入口。

状态是**进程内单例**: 本机单人用, 不需要持久化, 也只允许同时下一个(2-3G 的字节流, 并排下没有意义)。
"""
from __future__ import annotations

import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .. import resources

CATALOG = "llm_models.yaml"
MIRROR = "https://www.modelscope.cn/models"
_TIMEOUT = 30
_CHUNK = 1 << 20  # 1MB


class DownloadError(RuntimeError):
    """目录不合法 / 条目不存在 / 正在下载 —— 都带上给用户看的原因与 HTTP 状态码。"""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


# ---------- 目录 ----------

def catalog() -> list[dict]:
    """读模型目录。读不到 / 结构不对就报错 —— 不给空列表(空列表会让界面静默少一屏)。"""
    path = resources.config_path(CATALOG)
    if not path.is_file():
        raise DownloadError(f"缺模型目录: {path}", code=500)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("models")
    if not isinstance(items, list) or not items:
        raise DownloadError(f"{path} 里没有 models 列表", code=500)

    out: list[dict] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise DownloadError(f"{path}: models 里有非映射条目: {raw!r}", code=500)
        missing = [k for k in ("id", "name", "hint", "repo", "file", "size_gb") if k not in raw]
        if missing:
            raise DownloadError(f"{path}: 条目缺字段 {missing}: {raw!r}", code=500)
        # `file` 会被拼进下载地址、也会被当成本地落盘名 —— 只许是纯文件名。
        # 反斜杠要单独查: 在 POSIX 上它不算路径分隔符, Path(...).name 拦不住。
        fname = str(raw["file"])
        if fname != Path(fname).name or fname.startswith(".") or "\\" in fname:
            raise DownloadError(f"{path}: file 必须是纯文件名(不许带路径): {fname!r}", code=500)
        model_id = str(raw["id"])
        if model_id in seen:
            raise DownloadError(f"{path}: id 重复: {model_id!r}", code=500)
        seen.add(model_id)
        out.append({
            "id": model_id,
            "name": str(raw["name"]),
            "hint": str(raw["hint"]),
            "repo": str(raw["repo"]),
            "file": fname,
            "size_gb": float(raw["size_gb"]),
            "recommended": bool(raw.get("recommended", False)),
        })
    return out


def entry(model_id: str) -> dict:
    """按 id 取目录条目; 没有就报错(未知 id 不该悄悄变成"下点别的")。"""
    for item in catalog():
        if item["id"] == model_id:
            return item
    raise DownloadError(f"模型目录里没有这个 id: {model_id}")


def url_for(item: dict) -> str:
    """目录条目 → 下载地址。**只看目录**, 不看请求里的任何东西。"""
    return f"{MIRROR}/{item['repo']}/resolve/master/{urllib.parse.quote(item['file'])}"


def model_path(item: dict) -> Path:
    return resources.path("models") / item["file"]


def is_downloaded(item: dict) -> bool:
    return model_path(item).is_file()


def list_models() -> list[dict]:
    """给 `/api/models` 用: 目录 + 是否已下载(界面据此决定显示"下载"还是"可用")。"""
    return [{**item, "downloaded": is_downloaded(item)} for item in catalog()]


# ---------- 下载任务 ----------

class _Job:
    """一次只跑一个下载任务的状态。字段的读写都在锁里。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.id: str | None = None
        self.state = "idle"
        self.done_bytes = 0
        self.total_bytes: int | None = None
        self.error: str | None = None
        self.cancel = threading.Event()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "state": self.state,
                "done_bytes": self.done_bytes,
                "total_bytes": self.total_bytes,
                "error": self.error,
            }


_JOB = _Job()


def status() -> dict:
    return _JOB.snapshot()


def _part_of(item: dict) -> Path:
    dest = model_path(item)
    return dest.with_name(dest.name + ".part")


def start(model_id: str) -> dict:
    """起一个下载任务。未知 id / 已有任务 / 已下载过 —— 都是 400/409 + 原因。"""
    item = entry(model_id)
    if is_downloaded(item):
        raise DownloadError(
            f"{item['file']} 已经下载过了(在 var/models/)。要重新下就先删掉它。", code=409
        )
    with _JOB.lock:
        if _JOB.state == "downloading":
            raise DownloadError(
                f"已经有一个下载任务在跑({_JOB.id}), 等它结束或先取消", code=409
            )
        part = _part_of(item)
        _JOB.id = model_id
        _JOB.state = "downloading"
        _JOB.done_bytes = part.stat().st_size if part.is_file() else 0
        _JOB.total_bytes = None
        _JOB.error = None
        _JOB.cancel.clear()
    threading.Thread(target=_run, args=(item,), name="model-download", daemon=True).start()
    return status()


def cancel() -> dict:
    """请求取消。**保留 .part** —— 下次点下载从这里接着下。"""
    with _JOB.lock:
        if _JOB.state == "downloading":
            _JOB.cancel.set()
    return status()


def _run(item: dict) -> None:
    """下载线程: 流式写 .part, 成功后原子改名。任何失败都留下原因与 .part。"""
    dest = model_path(item)
    part = _part_of(item)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        start_at = part.stat().st_size if part.is_file() else 0

        req = urllib.request.Request(url_for(item))
        if start_at:
            req.add_header("Range", f"bytes={start_at}-")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 - 地址只来自仓库内的目录
            ranged = getattr(resp, "status", 200) == 206
            if start_at and not ranged:
                start_at = 0  # 服务端不支持续传: 老老实实从头下, 别把两段拼成坏文件
            length = resp.headers.get("Content-Length")
            total = int(length) + start_at if length and length.isdigit() else None
            with _JOB.lock:
                _JOB.done_bytes = start_at
                _JOB.total_bytes = total

            with open(part, "ab" if ranged else "wb") as fh:
                while True:
                    if _JOB.cancel.is_set():
                        with _JOB.lock:
                            _JOB.state = "cancelled"
                        return
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    with _JOB.lock:
                        _JOB.done_bytes += len(chunk)

        os.replace(part, dest)  # 原子: 界面上永远不会看到一个下了一半的 .gguf
        with _JOB.lock:
            _JOB.state = "done"
            _JOB.error = None
    except Exception as exc:  # noqa: BLE001 - 网络/磁盘/404 都要变成给用户看的 reason, 不吞
        with _JOB.lock:
            _JOB.state = "error"
            _JOB.error = f"{type(exc).__name__}: {exc}"
