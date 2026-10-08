"""Web 用户配置: 名字规则 / 归一化 / 结构校验 / 落盘(var/configs)。

与内置 `configs/*.yaml` 同 schema, 复用 `config_from_dict` 构造 Config。
只跟文件与词典打交道, 不碰 HTTP(那是 routes.py 的活)。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .. import resources
from ..config import Config, config_from_dict

# 用户配置名: 无点、无路径分隔符 —— 天然不与内置(带 .yaml)撞名, 也杜绝路径穿越
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
# 与 detectors.DETECTORS 的键一致(test_profiles 会核对, 防漂移)
DETECTOR_NAMES: tuple[str, ...] = ("rule", "dictionary", "onnx_ner", "llm_ner")
STRATEGY_VALUES: tuple[str, ...] = ("redact", "mask", "placeholder", "pseudonym", "remove", "keep")
EDITABLE_KEYS: tuple[str, ...] = ("strategies", "dictionary", "detectors", "onnx", "llm", "legacy_convert")
DEFAULT_REF = "default.yaml"


class ProfileError(ValueError):
    """用户配置非法(名字/结构/内置只读)。"""


def user_dir() -> Path:
    return resources.root() / "var" / "configs"


def is_builtin(ref: str) -> bool:
    return isinstance(ref, str) and ref.endswith(".yaml")


def _builtin_path(ref: str) -> Path:
    if Path(ref).name != ref or not ref.endswith(".yaml"):
        raise ProfileError(f"非法内置配置名: {ref!r}")
    return resources.config_path(ref)


def _user_path(name: str) -> Path:
    validate_name(name)
    return user_dir() / f"{name}.yaml"


def validate_name(name: str) -> None:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ProfileError(f"配置名只能是字母/数字/下划线/连字符, 1-32 位: {name!r}")


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path.name} yaml 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{path.name} 顶层不是映射")
    return data


def _default_data() -> dict:
    default = _read_yaml(_builtin_path(DEFAULT_REF))
    return {k: default.get(k) for k in EDITABLE_KEYS}


def normalize(data: dict) -> dict:
    """补齐缺失键(以 default.yaml 为底): 导入的半截 yaml 也可用, 盘上文件保持自包含。

    `onnx`/`llm` 是嵌套块, 整体缺失或只给部分子键(如仅 entity_map)都要补齐到
    default.yaml 的子键默认值, 否则会出现"build 得成、validate 却过不了"的错位。
    """
    if not isinstance(data, dict):
        raise ProfileError("配置必须是映射")
    base = _default_data()
    out = {k: data.get(k, base[k]) for k in EDITABLE_KEYS}
    for key in ("onnx", "llm"):
        value = data.get(key)
        if not isinstance(value, dict):
            out[key] = value if value is not None else base[key]
            continue
        out[key] = {**(base[key] or {}), **value}
    return out


def validate(data: dict) -> None:
    """结构校验; 不通过抛 ProfileError(点名哪里不对)。不看引擎是否真的能起(那是运行时预检)。"""
    data = normalize(data)
    strategies = data["strategies"]
    if not isinstance(strategies, dict):
        raise ProfileError("strategies 必须是映射")
    bad = sorted(f"{k}={v}" for k, v in strategies.items() if v not in STRATEGY_VALUES)
    if bad:
        raise ProfileError(f"未知策略值: {', '.join(bad)}（可选: {', '.join(STRATEGY_VALUES)}）")
    detectors = data["detectors"]
    if not isinstance(detectors, dict):
        raise ProfileError("detectors 必须是映射")
    unknown = sorted(k for k, v in detectors.items() if v and k not in DETECTOR_NAMES)
    if unknown:
        raise ProfileError(f"未知检测器: {', '.join(unknown)}（已登记: {', '.join(DETECTOR_NAMES)}）")
    if not any(detectors.get(n) for n in DETECTOR_NAMES):
        raise ProfileError("至少要启用一个检测器(全关 = 不产出脱敏结果)")
    if not isinstance(data["dictionary"], list):
        raise ProfileError("dictionary 必须是列表")
    onnx = data["onnx"]
    if not isinstance(onnx, dict) or not isinstance(onnx.get("model_dirs"), list):
        raise ProfileError("onnx.model_dirs 必须是列表")


def build_config(data: dict) -> Config:
    return config_from_dict(normalize(data))
