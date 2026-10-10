"""sidecar 生命周期: 桌面壳被强杀时, 后端不许变成占着端口的孤儿。

桌面壳的 SIGTERM quit 序列不触发窗口 close / 进程退出处理, 所以壳侧的
`child.kill()` 在强杀路径上根本没机会执行 —— 兜底必须在 Python 这一侧。
"""
from __future__ import annotations

import os
import threading
import time

ENV_EXIT_WITH_PARENT = "DOCANON_EXIT_WITH_PARENT"


def _win_pid_alive(pid: int) -> bool:
    """Windows: 这个 pid 还活着吗。

    `OpenProcess` 拿不到句柄 = 进程已经没了; 拿得到就等它 0 毫秒 —— 没等到超时说明还活着。
    只用 ctypes(标准库)是为了不为一个"别变孤儿"的兜底去装 pywin32。
    """
    import ctypes

    SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102   # 等超时 = 还没 signal = 进程还在
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # 必须显式声明: 句柄是指针宽度, 让它按默认的 c_int 走会在 64 位上被截断成随机值
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.WaitForSingleObject.restype = ctypes.c_uint32
    k32.CloseHandle.argtypes = [ctypes.c_void_p]

    handle = k32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return k32.WaitForSingleObject(ctypes.c_void_p(handle), 0) == WAIT_TIMEOUT
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))


def _parent_gone(origin: int) -> bool:
    """父进程是不是没了。

    POSIX 没有"父死子亡"的通用机制, 但父进程消失后本进程会被 reparent, getppid() 随之改变
    —— 盯住它就够了。**Windows 没有 reparent**: 父进程死了 getppid() 还是那个已经失效的 pid,
    所以只能反过来问系统"那个 pid 还在不在"。
    """
    if os.name != "nt":
        return os.getppid() != origin
    return not _win_pid_alive(origin)


def _watch_parent(origin: int, interval: float = 1.0) -> None:
    """父进程没了就自我了断(Ctrl+C / 正常退出都不走这里, 只有被强杀时才会触发)。"""
    while True:
        time.sleep(interval)
        if _parent_gone(origin):
            os._exit(0)


def _start_parent_watch() -> bool:
    """按环境变量决定是否开启父进程监视; 返回是否开启。默认关, 不影响交互式 `docanon web`。"""
    if os.environ.get(ENV_EXIT_WITH_PARENT, "").strip().lower() not in {"1", "true", "yes"}:
        return False
    threading.Thread(
        target=_watch_parent, args=(os.getppid(),), name="parent-watch", daemon=True
    ).start()
    return True
