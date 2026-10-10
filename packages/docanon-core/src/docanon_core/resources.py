"""资源根 + 仓库布局表: 随仓库/安装包走的路径都从这里取, 不要依赖当前工作目录。

解析顺序: `DOCANON_ROOT` 环境变量 > PyInstaller 冻结态的解包目录 > 从本文件逐级向上找到
含 `configs/default.yaml` 的目录(源码树 / editable 安装 / 打包根)。

只有"资源"走这里(配置文件、检测模型目录、Web 静态资源、内置样例);
命令行上的输入/输出路径仍然按调用者的工作目录, 那是用户参数, 不是资源。

**可写状态与资源分家**: 打包成 .app 后资源根在包内部(还可能被 macOS 的 App Translocation
挂到只读随机路径), 下载得到的模型、用户自建的配置都写不进去。所以 `WRITABLE` 里那几个键
按 `DOCANON_DATA` 解析 —— 桌面壳把它指到 `~/Library/Application Support/doc-anonymizer`;
源码树里不设这个变量, 两者同为资源根, 行为跟以前完全一样。

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
# 可写状态根: 只有打包/分发形态需要设; 不设就是资源根(源码树形态)。
ENV_DATA = "DOCANON_DATA"

# 仓库/打包根下的布局: 键 -> 相对资源根的路径。相对路径一律以 / 分隔(POSIX 风格)。
LAYOUT: dict[str, str] = {
    "configs": "configs",                     # 配置(default / legal / onnx / llm)
    "web": "apps/web/dist",                   # 前端构建产物(Vite 输出; 源码在 apps/web/src)
    "vendor": "var/vendor/file-viewer",  # file-viewer 预览资源(可选, fetch_file_viewer.sh 下载)
    "samples": "samples",                     # 内置样例(Web 预设 + 测试数据)
    "models": "var/models",                      # 模型权重(可选, 下载得到)
    "user_configs": "var/configs",            # Web 里用户自建的方案(可选, 用户写出来的)
    "libreoffice": "var/libreoffice",   # 旧版 Office 转换用(可选, fetch_libreoffice.sh 下载)
    "scripts": "scripts",                     # 开发者脚本
}

# 上面这些键里, 哪些是"运行期可写状态"(按数据根解析), 哪些是"随包发布的只读资源"(按资源根解析)。
WRITABLE: frozenset[str] = frozenset({"models", "user_configs"})

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


def data_root() -> Path:
    """可写状态(下载的模型、用户方案)的根。没设 DOCANON_DATA 就是资源根(源码树形态)。

    打包形态下资源根在 .app 里面, 可能还是只读的随机挂载点(App Translocation), 所以壳会把它
    指到用户的 Application Support 目录。这里**不**在目录不存在时兜回资源根 —— 宁可写失败报错,
    也不要悄悄把 GB 级模型塞进安装包。
    """
    override = os.environ.get(ENV_DATA)
    return Path(override).expanduser().resolve() if override else root()


def path(key: str) -> Path:
    """布局表里的某一项。可写状态键按数据根解析, 其余按资源根解析(见 WRITABLE)。"""
    try:
        rel = LAYOUT[key]
    except KeyError:  # pragma: no cover - 只在写错键名时触发
        raise KeyError(f"LAYOUT 里没有 {key!r}; 已登记: {', '.join(sorted(LAYOUT))}") from None
    base = data_root() if key in WRITABLE else root()
    return base / rel


def resolve(path: str | Path) -> Path:
    """配置里写的相对路径按资源根解析; 绝对路径与 ~ 原样尊重。"""
    p = Path(path).expanduser()
    return p if p.is_absolute() else root() / p


def resolve_model_dir(path: str | Path) -> Path:
    """模型目录(config.onnx.model_dirs): 相对路径按**数据根**解析。

    跟 `resolve` 分开是因为它们落在不同的根上: 配置/前端/样例是随包发布的只读资源, 模型是
    下载到用户目录的可写状态。混用会在打包后表现为"模型明明下好了却加载不到"。
    """
    p = Path(path).expanduser()
    return p if p.is_absolute() else data_root() / p


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
