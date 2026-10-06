"""资源根: 随仓库/安装包走的路径都从这里取, 不要依赖当前工作目录。

优先级: DOCANON_ROOT 环境变量 > PyInstaller 冻结态的解包目录 > 本文件的仓库根。
只有"资源"走这里(配置里的检测模型目录、-c 配置文件、Web 静态资源);
命令行上的输入/输出路径仍然按调用者的工作目录, 那是用户参数, 不是资源。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_ROOT = "DOCANON_ROOT"


def root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen)
    return Path(__file__).resolve().parents[2]


def resolve(path: str | Path) -> Path:
    """配置里写的相对路径按资源根解析; 绝对路径与 ~ 原样尊重。"""
    p = Path(path).expanduser()
    return p if p.is_absolute() else root() / p


def config_path(name: str) -> Path:
    return root() / "configs" / name


def web_index() -> Path:
    return root() / "apps" / "web" / "index.html"


def vendor_dir() -> Path:
    return root() / "apps" / "web" / "vendor" / "file-viewer"


def samples_dir() -> Path:
    return root() / "samples"
