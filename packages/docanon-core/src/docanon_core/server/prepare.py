"""首次"初始化": 按当前方案把缺的东西补齐(下载识别模型), 让用户点一下就能用。

为什么要它: 模型不进安装包(体积 5.9G)。但界面默认方案「通用」**依赖 ONNX 模型**, 而以前
取模型只有命令行脚本 —— 用户装完选默认方案, 第一次跑就撞上"少一层检测器"。这个模块把
"按方案补齐" 做成一个后台任务, 界面只说"正在初始化"。

三条设计:
- **对用户不出现技术词**: 状态只有 idle/running/done/error + 字节数, 文案交给界面(一句"正在初始化")。
- **先测速再选源**: 国内直连 huggingface.co 常不可达, 所以先对候选端点各取一小段比速度, 挑快的再用。
  地址一律由仓库内的目录(`configs/onnx_models.yaml`)拼出 —— 不接受请求里的 URL(否则等于任意下载口)。
- **少一个文件就不算就绪**: 每个文件先写 `.part` 再原子改名; 只有目录里文件齐了才报 done,
  否则宁可报错也不让"少了识别层"的结果蒙混过去。

大模型(gguf)不在本模块: 它已有自己的单文件下载(`downloads.py`), 这里只负责**触发与转述**进度。
"""
from __future__ import annotations

import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .. import resources
from ..config import Config
from . import downloads

CATALOG = "onnx_models.yaml"

# 候选下载源(按"国内可达性"排序只是初值, 真正的顺序由测速决定)
ENDPOINTS: tuple[str, ...] = (
    "https://hf-mirror.com",     # 国内镜像
    "https://huggingface.co",    # 官方源(部分网络不可达)
)

_TIMEOUT = 30
_CHUNK = 1 << 20            # 1MB
_SPEED_BYTES = 1 << 18      # 测速只取 256KB
_SPEED_TIMEOUT = 20         # 镜像首字节实测能到 6s(冷启动), 给宽一点, 免得把可用的源误判成不可用

# 必须带 User-Agent: hf-mirror 对没有 UA 的请求回 403(实测 config.json 403 / model.onnx 206),
# 少了它会出现"小文件全都下不动"的假故障。
_UA = "docanon/0.2 (+local document redactor)"

# 用来测速的文件: 权重最大、最能反映真实带宽。按名字找, 不按"哪个文件名最长"(那会挑中 json)。
_WEIGHT_NAMES = ("model.onnx.data", "model.onnx")


def _headers(extra: dict | None = None) -> dict:
    h = {"User-Agent": _UA}
    if extra:
        h.update(extra)
    return h


class PrepareError(RuntimeError):
    """目录不合法 / 没源可用 / 任务冲突 —— 都带一句给用户看的话与 HTTP 状态码。"""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


# ---------- 目录 ----------

def catalog() -> list[dict]:
    """读识别模型目录。读不到 / 结构不对就报错(不给空列表 —— 那会让"初始化"静默什么都不做)。"""
    path = resources.config_path(CATALOG)
    if not path.is_file():
        raise PrepareError(f"缺模型目录: {path}", code=500)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get("models")
    if not isinstance(items, list) or not items:
        raise PrepareError(f"{path} 里没有 models 列表", code=500)

    out: list[dict] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise PrepareError(f"{path}: models 里有非映射条目: {raw!r}", code=500)
        missing = [k for k in ("id", "repo", "files") if k not in raw]
        if missing:
            raise PrepareError(f"{path}: 条目缺字段 {missing}: {raw!r}", code=500)
        files = raw["files"]
        if not isinstance(files, list) or not files:
            raise PrepareError(f"{path}: files 必须是非空列表: {raw!r}", code=500)
        model_id = str(raw["id"])
        if model_id in seen:
            raise PrepareError(f"{path}: id 重复: {model_id!r}", code=500)
        # id 会当目录名用: 只许纯名字(不许带路径或退到上级)
        if model_id != Path(model_id).name or model_id.startswith("."):
            raise PrepareError(f"{path}: id 必须是纯名字(不许带路径): {model_id!r}", code=500)
        for f in files:
            if str(f) != Path(str(f)).name or "\\" in str(f):
                raise PrepareError(f"{path}: files 只许纯文件名: {f!r}", code=500)
        seen.add(model_id)
        out.append({
            "id": model_id,
            "repo": str(raw["repo"]),
            "files": [str(f) for f in files],
            "size_mb": int(raw.get("size_mb", 0) or 0),
        })
    return out


def dir_for(model_id: str) -> Path:
    return resources.path("models") / "onnx" / model_id


def installed(item: dict) -> bool:
    """文件齐了才算装好。少一个都当没装 —— 否则运行时会"少一层"。"""
    d = dir_for(item["id"])
    return all((d / f).is_file() and (d / f).stat().st_size > 0 for f in item["files"])


def missing_ids(cfg: Config) -> list[str]:
    """当前方案要用、但本机还没有的识别模型 id(按目录顺序)。

    `cfg.onnx.model_dirs` 里给的是相对资源根的路径(如 var/models/onnx/gyr66), 这里取目录名当 id。
    目录里没登记的(用户自备模型)不参与自动下载 —— 猜不得。
    """
    if not cfg.detectors.get("onnx_ner"):
        return []
    known = {item["id"]: item for item in catalog()}
    want: list[str] = []
    for d in cfg.onnx.model_dirs:
        name = Path(str(d).rstrip("/")).name
        item = known.get(name)
        if item and not installed(item):
            want.append(name)
    return want


def needed(cfg: Config) -> dict:
    """当前方案要补什么。给界面判断"要不要初始化"用(不含技术细节)。"""
    onnx = missing_ids(cfg)
    llm_id = None
    if cfg.detectors.get("llm_ner") and cfg.llm_model_id:
        try:
            item = downloads.entry(cfg.llm_model_id)
            if not downloads.is_downloaded(item):
                llm_id = cfg.llm_model_id
        except downloads.DownloadError:
            llm_id = cfg.llm_model_id   # 目录里查不到也让上层去试, 由下载任务给出原因
    return {"onnx": onnx, "llm": llm_id, "ready": not onnx and not llm_id}


# ---------- 测速选源 ----------

def _weight_of(item: dict) -> str:
    """挑测速用的文件: 优先权重(数据量大, 才测得出真带宽), 没有就退回第一个文件。"""
    for name in _WEIGHT_NAMES:
        if name in item["files"]:
            return name
    return item["files"][0]


def _endpoint_speed(base: str, item: dict) -> float:
    """取该源上权重文件的前 256KB, 返回字节/秒。失败返回 0(视为不可用)。"""
    fname = _weight_of(item)
    url = f"{base}/{item['repo']}/resolve/main/{urllib.parse.quote(fname)}"
    req = urllib.request.Request(url, headers=_headers({"Range": f"bytes=0-{_SPEED_BYTES - 1}"}))
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=_SPEED_TIMEOUT) as resp:  # noqa: S310 - 地址只来自仓库内目录
            got = resp.read(_SPEED_BYTES)
    except Exception:  # noqa: BLE001 - 网络问题一律当"这个源不可用", 换下一个
        return 0.0
    elapsed = max(time.monotonic() - started, 1e-3)
    return len(got) / elapsed


def pick_endpoint(item: dict) -> str:
    """挑最快的可用源。一个都不通就报错(不静默换到"猜"的地址)。"""
    best, best_speed = "", 0.0
    for base in ENDPOINTS:
        speed = _endpoint_speed(base, item)
        if speed > best_speed:
            best, best_speed = base, speed
    if not best:
        raise PrepareError("没有可用的下载源，请检查网络后重试", code=502)
    return best


# ---------- 任务 ----------

class _Job:
    """一次只跑一个初始化任务。字段读写都在锁里。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = "idle"          # idle | running | done | error | cancelled
        self.done_bytes = 0
        self.total_bytes: int | None = None
        self.error: str | None = None
        self.cancel = threading.Event()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "state": self.state,
                "done_bytes": self.done_bytes,
                "total_bytes": self.total_bytes,
                "error": self.error,
            }


_JOB = _Job()


def status() -> dict:
    """统一的初始化状态: 本模块的 ONNX 任务, 或转述大模型下载任务的进度。

    界面只认这一份 —— 不然前端要认识两套下载, 术语就漏出去了。
    大模型那条要单独看: 本模块把它的下载**交出去**之后立刻算自己完事, 但那个大文件还在下。
    """
    # 注意: 别在持锁时调 snapshot()(它也要拿同一把非可重入的锁) —— 先读状态再取快照
    with _JOB.lock:
        running = _JOB.state == "running"
    if running:
        return _JOB.snapshot()

    dl = downloads.status()
    if dl["state"] == "downloading":
        return {"state": "running", "done_bytes": dl["done_bytes"],
                "total_bytes": dl["total_bytes"], "error": None}
    if dl["state"] == "error":
        return {"state": "error", "done_bytes": dl["done_bytes"],
                "total_bytes": dl["total_bytes"], "error": dl["error"]}
    return _JOB.snapshot()


def cancel() -> dict:
    """请求取消。已下好的文件保留 —— 下次从这里接着补。"""
    with _JOB.lock:
        if _JOB.state == "running":
            _JOB.cancel.set()
    downloads.cancel()
    return status()


def start(cfg: Config) -> dict:
    """按方案补齐。已经齐了就返回 done; 正跑着就返回当前进度; 缺什么就下什么。"""
    plan = needed(cfg)
    if plan["ready"]:
        with _JOB.lock:
            _JOB.state = "done"
            _JOB.error = None
            _JOB.done_bytes = _JOB.total_bytes or 0
        return status()
    with _JOB.lock:
        if _JOB.state == "running":
            raise PrepareError("正在准备中，请稍候", code=409)
        _JOB.state = "running"
        _JOB.done_bytes = 0
        _JOB.total_bytes = None
        _JOB.error = None
        _JOB.cancel.clear()
    threading.Thread(target=_run, args=(cfg, plan), name="prepare", daemon=True).start()
    return status()


def _run(cfg: Config, plan: dict) -> None:
    """初始化线程: 先补齐识别模型, 再交给大模型下载(如果也需要)。

    任何失败都变一句给用户看的话; 半个文件用 `.part` 挡住, 不会被当成"已装好"。
    """
    try:
        items = {item["id"]: item for item in catalog()}
        for model_id in plan["onnx"]:
            _download_model(items[model_id])
        if plan["llm"]:
            downloads.start(plan["llm"])     # 大模型那条复用现成能力
        with _JOB.lock:
            _JOB.state = "done"
            _JOB.error = None
    except downloads.DownloadError as exc:
        with _JOB.lock:
            _JOB.state = "error"
            _JOB.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - 网络/磁盘/取消都要变成能看懂的 reason
        with _JOB.lock:
            cancelled = _JOB.cancel.is_set()
            _JOB.state = "cancelled" if cancelled else "error"
            _JOB.error = None if cancelled else f"{type(exc).__name__}: {exc}"


def _download_model(item: dict) -> None:
    """把一个模型目录里的文件逐个下回来。全齐了才算完; 中途取消就停在 .part。"""
    base = pick_endpoint(item)
    dest_dir = dir_for(item["id"])
    dest_dir.mkdir(parents=True, exist_ok=True)

    todo = [f for f in item["files"] if not (dest_dir / f).is_file()]
    total = _probe_total(base, item, todo)
    with _JOB.lock:
        _JOB.total_bytes = total
        _JOB.done_bytes = sum(
            (dest_dir / f).stat().st_size for f in item["files"] if (dest_dir / f).is_file()
        )

    for fname in todo:
        if _JOB.cancel.is_set():
            raise RuntimeError("cancelled")
        _fetch(base, item["repo"], fname, dest_dir / fname)

    if not installed(item):
        raise RuntimeError("文件没下全")   # 不许把"少一层"报成就绪


def _probe_total(base: str, item: dict, todo: list[str]) -> int | None:
    """问一遍待下文件的体积, 好让进度条有总量。

    三个实测出来的坑: 镜像对 HEAD 与无 UA 的请求回 403; 小文件走分块传输、不给 Content-Length;
    只有权重支持 Range(`Content-Range` 尾部才是真大小)。所以拿不全就退回目录里的 `size_mb` 估个量级
    —— 进度条只要"大概到哪了", 不必字节精确。都拿不到才返回 None(界面退化成只显示已下多少)。
    """
    total = 0
    for fname in todo:
        url = f"{base}/{item['repo']}/resolve/main/{urllib.parse.quote(fname)}"
        try:
            req = urllib.request.Request(url, headers=_headers({"Range": "bytes=0-0"}))
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
                size = _size_from(resp.headers)
        except Exception:  # noqa: BLE001 - 拿不到总量不影响下载, 只是进度没有百分比
            size = None
        if size is None:
            est = int(item.get("size_mb", 0) or 0) * 1024 * 1024
            return est or None
        total += size
    return total or None


def _size_from(headers) -> int | None:
    """从响应头取文件总大小: 优先 `Content-Range` 的尾部(带 Range 时), 退回 `Content-Length`。"""
    cr = headers.get("Content-Range")
    if cr and "/" in cr:
        tail = cr.rsplit("/", 1)[1].strip()
        if tail.isdigit():
            return int(tail)
    cl = headers.get("Content-Length")
    if cl and cl.isdigit():
        return int(cl)
    return None


def _fetch(base: str, repo: str, fname: str, dest: Path) -> None:
    """单文件: 先写 `.part`, 下完原子改名 —— 界面上永远看不到半截权重。"""
    url = f"{base}/{repo}/resolve/main/{urllib.parse.quote(fname)}"
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        start_at = part.stat().st_size if part.is_file() else 0
        req = urllib.request.Request(
            url, headers=_headers({"Range": f"bytes={start_at}-"} if start_at else None)
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            ranged = getattr(resp, "status", 200) == 206
            if start_at and not ranged:
                start_at = 0
            with open(part, "ab" if ranged else "wb") as fh:
                while True:
                    if _JOB.cancel.is_set():
                        raise RuntimeError("cancelled")
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    with _JOB.lock:
                        _JOB.done_bytes += len(chunk)
        part.replace(dest)
    except urllib.error.HTTPError as exc:
        raise PrepareError(f"下载失败（{exc.code}）：请检查网络后重试", code=502) from exc
    except urllib.error.URLError as exc:
        raise PrepareError("网络不可用：请检查网络后重试", code=502) from exc
