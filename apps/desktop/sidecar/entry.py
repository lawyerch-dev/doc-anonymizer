"""桌面壳的 Python 侧车入口。

与源码态的 `python -m docanon_core.cli` **完全等价** —— 壳那边两条路给的是同一串参数
(`web --no-browser -p <port> -c <config>`), 所以换解释器/换可执行文件都不需要改壳的调用代码。

打成可执行文件后 `sys.argv[0]` 是这个可执行文件, 命令行参数不变, 因此这里直接把 argv
交给 cli.main(), 不自己解析。
"""
from __future__ import annotations

import os
import sys

# Windows 上把侧车当 GUI 进程拉起时(没有可继承的控制台句柄)sys.stdout/stderr 会是 None,
# 而 docanon 到处都在 print 日志与警告 —— 不兜住就会在"只是想说句话"的地方以
# AttributeError 崩掉整个后端。这里在 import 之前先把它们指到空设备。
for _name in ("stdout", "stderr"):
    if getattr(sys, _name, None) is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))

from docanon_core.cli import main  # noqa: E402 - 必须在上面那个兜底之后

if __name__ == "__main__":
    raise SystemExit(main())
