"""资源根 + 仓库布局表: 随仓库/安装包走的路径都从这里取, 不要依赖当前工作目录。

解析顺序: `DOCANON_ROOT` 环境变量 > PyInstaller 冻结态的解包目录 > 从本文件逐级向上找到
含 `configs/default.yaml` 的目录(源码树 / editable 安装 / 打包根)。

只有"资源"走这里(配置文件、检测模型目录、Web 静态资源、内置样例);
命令行上的输入/输出路径仍然按调用者的工作目录, 那是用户参数, 不是资源。

**所有布局知识都在下面的 LAYOUT 里** —— 谁要挪目录, 只改这一处; `tests/test_layout.py`
会立刻告诉你哪里对不上, 而不是等运行时在别处炸。

部署契约(与根 pyproject.toml 的说明同源): 只支持 **editable 安装** 与 **打包根** 两种形态,
不做 wheel 自包含(前端 vendor 232MB、模型 GB 级, 本来就不该进包)。非 editable 安装由
`ResourceRootError` 明确报错, 而不是退化成"读到空配置还装没事"(见 `config.load_config`)。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_ROOT = "DOCANON_ROOT"

# 仓库/打包根下的布局: 键 -> 相对资源根的路径。相对路径一律以 / 分隔(POSIX 风格)。
LAYOUT: dict[str, str] = {
    "configs": "configs",                     # 配置(default / legal / onnx / llm)
    "web": "apps/web",                        # 前端静态件(index.html / app.css / app.js)
    "vendor": "var/vendor/file-viewer",  # file-viewer 预览资源(可选, fetch_file_viewer.sh 下载)
    "samples": "samples",                     # 内置样例(Web 预设 + 测试数据)
    "models": "var/models",                      # 模型权重(可选, 下载得到)
    "libreoffice": "var/libreoffice",   # 旧版 Office 转换用(可选, fetch_libreoffice.sh 下载)
    "scripts": "scripts",                     # 开发者脚本
}

# 任何一份能用的源码树/打包根都必须有的资源; 其余(vendor/models)是下载得到的, 缺了只影响功能。
REQUIRED: tuple[str, ...] = ("configs", "web", "samples")

# 资源根的标记文件: 用 configs 里的默认配置认根, 所以它必须在 LAYOUT 里且保持是个文件。
MARKER = Path(LAYOUT["configs"]) / "default.yaml"


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


def path(key: str) -> Path:
    """布局表里的某一项(按资源根解析)。"""
    try:
        rel = LAYOUT[key]
    except KeyError:  # pragma: no cover - 只在写错键名时触发
        raise KeyError(f"LAYOUT 里没有 {key!r}; 已登记: {', '.join(sorted(LAYOUT))}") from None
    return root() / rel


def resolve(path: str | Path) -> Path:
    """配置里写的相对路径按资源根解析; 绝对路径与 ~ 原样尊重。"""
    p = Path(path).expanduser()
    return p if p.is_absolute() else root() / p


def missing() -> list[tuple[str, Path]]:
    """必需的资源里缺了哪几项(键, 绝对路径); 全齐就是空列表。"""
    return [(key, path(key)) for key in REQUIRED if not path(key).exists()]


def config_path(name: str) -> Path:
    return path("configs") / name


def web_index() -> Path:
    return path("web") / "index.html"


def vendor_dir() -> Path:
    return path("vendor")


def samples_dir() -> Path:
    return path("samples")


def models_dir() -> Path:
    return path("models")


def libreoffice_dir() -> Path:
    return path("libreoffice")
