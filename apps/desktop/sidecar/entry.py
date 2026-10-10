"""桌面壳的 Python 侧车入口。

与源码态的 `python -m docanon_core.cli` **完全等价** —— 壳那边两条路给的是同一串参数
(`web --no-browser -p <port> -c <config>`), 所以换解释器/换可执行文件都不需要改壳的调用代码。

打成单文件可执行后 `sys.argv[0]` 是这个可执行文件, 命令行参数不变, 因此这里直接把 argv
交给 cli.main(), 不自己解析。
"""
from __future__ import annotations

from docanon_core.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
