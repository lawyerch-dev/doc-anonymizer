"""资源根: 随仓库/安装包走的路径都从这里取, 不要依赖当前工作目录。

优先级: DOCANON_ROOT 环境变量 > PyInstaller 冻结态的解包目录 > 从本文件逐级向上找到
含 `configs/default.yaml` 的目录(源码树 / editable 安装 / 打包根)。

只有"资源"走这里(配置里的检测模型目录、-c 配置文件、Web 静态资源);
命令行上的输入/输出路径仍然按调用者的工作目录, 那是用户参数, 不是资源。

解析不出来时必须报错, 不许猜: `parents[2]` 那种写法在非 editable 安装下会指到
site-packages, 那里当然没有 configs/ —— 猜错的后果是读到一份空配置, 而"空配置"和
"一层检测都没启用"长得一模一样(见 `config.load_config`)。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_ROOT = "DOCANON_ROOT"

# 资源根的标记文件: 有这个才认这个目录。与 config_path("default.yaml") 同源, 不要改两处。
MARKER = Path("configs") / "default.yaml"


class ResourceRootError(RuntimeError):
    """找不到资源根。调用方应当直接失败, 而不是退回一个猜出来的目录。"""


def find_root(start: str | Path | None = None) -> Path:
    """从 start(默认本文件)逐级向上找资源根; 找不到就报错, 并列出试过的目录。"""
    origin = Path(start) if start is not None else Path(__file__)
    origin = origin.resolve()
    tried: list[Path] = []
    for candidate in (origin, *origin.parents):
        tried.append(candidate)
        if (candidate / MARKER).is_file():
            return candidate
    raise ResourceRootError(
        f"找不到 docanon 资源根(需要含 {MARKER} 的目录); 已向上查找: "
        + ", ".join(str(p) for p in tried)
        + f"。若这是非 editable 安装(pip install 到了别处), 请设置 {ENV_ROOT} "
        "指向仓库根或打包根。"
    )


def root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen)
    return find_root()


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
