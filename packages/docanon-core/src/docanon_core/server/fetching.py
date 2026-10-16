"""单文件「流式下载 + 断点续传 + 原子落盘」的**唯一实现**。

`downloads.py`(大模型 gguf)与 `prepare.py`(识别模型)都要下大文件, 走的是同一件事:
`.part` → 带 Range 续传 → 服务端支持就接着写、不支持就从头 → 下完 `os.replace` 原子改名。
这段一旦两处各写一遍, "续传把两段拼成坏文件"这类问题就会各修各的 —— 所以收在这里。

进度与取消靠回调/事件交回调用方, 本模块不认识任何一个下载任务的状态机。
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

_CHUNK = 1 << 20   # 1MB
TIMEOUT = 30       # 秒; 调用方可传自己的


class CancelledDownload(RuntimeError):
    """下载被取消: `.part` 留着, 下次从这里接着下。"""


def size_from(headers) -> int | None:
    """响应头里的文件大小: 优先 `Content-Range` 的尾部(带 Range 时是全量), 退回 `Content-Length`。"""
    cr = headers.get("Content-Range")
    if cr and "/" in cr:
        tail = cr.rsplit("/", 1)[1].strip()
        if tail.isdigit():
            return int(tail)
    cl = headers.get("Content-Length")
    if cl and cl.isdigit():
        return int(cl)
    return None


def stream_to_file(
    url: str,
    dest: str | Path,
    *,
    headers: dict | None = None,
    cancel=None,
    on_total=None,
    on_progress=None,
    timeout: int = TIMEOUT,
) -> None:
    """把 `url` 流式写进 `dest`: `.part` + Range 续传 + 原子改名。

    - 已有 `.part` 就带 `Range` 续传; 服务端不支持(非 206)则从头下, 绝不把两段拼成坏文件。
    - `on_total(total_or_none)` 在拿到总大小时回调一次(已含续传起点); `on_progress(n)` 每写一块回调。
    - `cancel`(threading.Event 或 None)置位后立刻停下并抛 `CancelledDownload`。
    """
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    start_at = part.stat().st_size if part.is_file() else 0

    req = urllib.request.Request(url, headers=dict(headers or {}))
    if start_at:
        req.add_header("Range", f"bytes={start_at}-")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 地址只来自仓库内的目录
        ranged = getattr(resp, "status", 200) == 206
        if start_at and not ranged:
            start_at = 0   # 服务端不支持续传: 从头下
        # 全量大小: Content-Range 的尾部就是全量; 只有 Content-Length 时它只是本次请求的字节数
        # (续传时是剩余量), 还要补上起点。
        cr = resp.headers.get("Content-Range")
        if cr and "/" in cr and cr.rsplit("/", 1)[1].strip().isdigit():
            total = int(cr.rsplit("/", 1)[1])
        else:
            cl = resp.headers.get("Content-Length")
            total = int(cl) + start_at if (cl and cl.isdigit()) else None
        if on_total is not None:
            on_total(total)
        with open(part, "ab" if ranged else "wb") as fh:
            while True:
                if cancel is not None and cancel.is_set():
                    raise CancelledDownload()
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                if on_progress is not None:
                    on_progress(len(chunk))
    os.replace(part, dest)   # 原子: 界面上永远看不到半截权重
