"""sidecar 生命周期: 桌面壳被强杀时, 后端不许变成占着端口的孤儿。

Electrobun 自己的 SIGTERM quit 序列不触发 JS 的 window close / process.exit, 所以壳侧的
`child.kill()` 在强杀路径上根本没机会执行 —— 兜底必须在 Python 这一侧。
"""
from __future__ import annotations

import os
import threading
import time

ENV_EXIT_WITH_PARENT = "DOCANON_EXIT_WITH_PARENT"


def _watch_parent(origin: int, interval: float = 1.0) -> None:
    """父进程没了就自我了断(Ctrl+C / 正常退出都不走这里, 只有被强杀时才会触发)。

    POSIX 没有"父死子亡"的通用机制, 但父进程消失后本进程会被 reparent, getppid() 随之改变
    —— 盯住它就够了。
    """
    while True:
        time.sleep(interval)
        if os.getppid() != origin:
            os._exit(0)


def _start_parent_watch() -> bool:
    """按环境变量决定是否开启父进程监视; 返回是否开启。默认关, 不影响交互式 `docanon web`。"""
    if os.environ.get(ENV_EXIT_WITH_PARENT, "").strip().lower() not in {"1", "true", "yes"}:
        return False
    threading.Thread(
        target=_watch_parent, args=(os.getppid(),), name="parent-watch", daemon=True
    ).start()
    return True
