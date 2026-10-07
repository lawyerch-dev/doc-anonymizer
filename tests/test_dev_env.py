"""开发环境: 字节码缓存不许在源码树里长出来。

默认每个包/每个测试目录都会生成一个 `__pycache__`; `scripts/setup_dev.sh` 把它**重定向**到
`var/pycache` —— 于是 `.venv` 里的任何 Python(pytest / `docanon` / 脚本 / 壳的 sidecar)都只往那一处写,
源码树保持干净, 而字节码带来的启动速度不丢。

为什么不是"完全不写字节码"(`PYTHONDONTWRITEBYTECODE=1`): 实测那样每次都要重编译所有导入,
整套测试从 5.12s 涨到 6.24s。重定向是同一份干净、但不付这份代价。

没有做重定向的环境(典型: 用系统 python 而不是 `.venv` 跑测试)会让这条测试红 —— 这是故意的,
`AGENTS.md` 本来就写明测试必须用 `.venv/bin/python`。
"""
from __future__ import annotations

import os
import pathlib
import stat

REPO = pathlib.Path(__file__).resolve().parents[1]
# 这些目录里可以随便长(.venv 与 var 是本地状态; node_modules 是壳/浏览器检查的依赖)
SKIP_DIRS = {".git", ".venv", "var", "node_modules"}


def _bytecode_dirs() -> list[pathlib.Path]:
    hits: list[pathlib.Path] = []
    for dirpath, dirnames, _ in os.walk(REPO):
        keep = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            if name == "__pycache__":
                hits.append(pathlib.Path(dirpath) / name)
                continue
            keep.append(name)
        dirnames[:] = keep
    return hits


def test_source_tree_has_no_bytecode_cache():
    found = _bytecode_dirs()
    listed = ", ".join(str(p.relative_to(REPO)) for p in found[:5])
    assert not found, (
        f"源码树里冒出了 {len(found)} 个 __pycache__({listed} …): "
        "跑 ./scripts/setup_dev.sh 把字节码缓存重定向到 var/pycache"
    )


def test_scripts_are_executable():
    """文档里都写成 `./scripts/x.sh`, 那这些脚本就得真的可执行(踩过一次: fetch_file_viewer.sh 少了 x 位)。"""
    scripts = sorted((REPO / "scripts").glob("*.sh"))
    assert scripts, "scripts/ 下没有 .sh?"
    lost = [p.name for p in scripts if not p.stat().st_mode & stat.S_IXUSR]
    assert not lost, f"这些脚本丢了可执行位, 按文档 ./ 跑不起来: {lost}"


def test_venv_carries_the_pycache_hook():
    """机制自检: `.venv` 里应当装着那个 sitecustomize(否则只有显式设环境变量才干净)。"""
    import sys
    import sysconfig

    import pytest

    if sys.prefix == sys.base_prefix:  # 不是 venv 解释器(用系统 python 跑测试)
        pytest.skip("当前不是 venv 解释器; 用 .venv/bin/python 跑才会检查这一条")
    hook = pathlib.Path(sysconfig.get_paths()["purelib"]) / "sitecustomize.py"
    assert hook.is_file(), "venv 里没有 sitecustomize.py —— 跑 ./scripts/setup_dev.sh 装它"
    assert "pycache_prefix" in hook.read_text(encoding="utf-8")
