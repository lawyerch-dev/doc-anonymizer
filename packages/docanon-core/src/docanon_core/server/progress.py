"""跑一份文档时的进度与取消: 前端按 job id 轮询这里, 不靠流式响应。

为什么要有: 最准档跑一份 5000 字的合同要 37 秒(其中识别 36 秒), 而界面只有一句"脱敏中…" ——
用户不知道是在转格式、在识别、还是卡死了, 也没法中止。

做法: `/api/anonymize` 仍然是**一次同步请求**, 前端另开一个轮询读状态。这样不用改 HTTP 语义,
也不用把 pipeline 拆成分步接口。单进程单人用, 一次只跑一个任务(与 `downloads.py` 同一个假设)。

job id 由前端生成、会被当字典键, 所以只收 `^[A-Za-z0-9_-]{1,32}$`; 表按条数封顶, 免得长期运行攒垃圾。
"""
from __future__ import annotations

import re
import threading

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_JOBS = 16

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


class BadJobId(ValueError):
    """job id 不合法(要当字典键用, 不能随便收)。"""


def begin(job_id: str) -> threading.Event:
    """登记一个任务, 返回它的取消信号(交给 pipeline 轮询)。"""
    if not NAME_RE.match(job_id or ""):
        raise BadJobId(f"非法 job id: {job_id!r}")
    cancel = threading.Event()
    with _lock:
        if len(_jobs) >= MAX_JOBS:  # 攒多了先丢最早的一半(都是已经跑完的)
            for old in list(_jobs)[: MAX_JOBS // 2]:
                _jobs.pop(old, None)
        _jobs[job_id] = {
            "stage": "extract", "done": 0, "total": 0, "cancelled": False, "cancel": cancel,
        }
    return cancel


def update(job_id: str, stage: str, done: int = 0, total: int = 0) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(stage=stage, done=done, total=total)


def finish(job_id: str) -> None:
    """跑完就收尾(成功/失败/取消都一样), 前端看到 `done` 就停止轮询。"""
    with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["stage"] = "done"
            job["cancel"].set()


def cancel(job_id: str) -> bool:
    """请求取消。真正停下来靠 pipeline 在每块文字之间查这个信号。"""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return False
        job["cancelled"] = True
        job["cancel"].set()
        return True


def state(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return {"stage": "unknown", "done": 0, "total": 0, "cancelled": False}
        return {
            "stage": job["stage"],
            "done": job["done"],
            "total": job["total"],
            "cancelled": job["cancelled"],
        }


def clear() -> None:
    """测试用: 清掉所有任务状态。"""
    with _lock:
        _jobs.clear()
