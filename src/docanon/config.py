"""配置加载。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import resources
from .llm.client import LLMConfig

# 各模型自己的标签 -> 本项目的实体类型。这是 app 的词汇表, 所以放在 app 侧:
# 引擎只收一张映射表进来, 它不认识 PERSON/ORG/CUSTOM 这些名字。
# 没被映射到的标签会被该引擎直接忽略 —— 改这里之前先确认你不想让那个标签出结果。
DEFAULT_ONNX_ENTITY_MAP: dict[str, str] = {
    # pii-engineer/PII-Engineer-Chinese-NER
    "person": "PERSON",
    "phone_number": "PHONE",
    "nric": "ID_CARD",
    "street_address": "LOCATION",
    "date_of_birth": "DOB",
    # protectai/gyr66 (CLUENER 系)
    "name": "PERSON",
    "organization": "ORG",
    "company": "ORG",
    "government": "ORG",
    "address": "LOCATION",
    "mobile": "PHONE",
    "email": "EMAIL",
    "position": "POSITION",
    "qq": "CUSTOM",
    "vx": "CUSTOM",
}


@dataclass
class OnnxConfig:
    model_dirs: list[str] = field(
        default_factory=lambda: ["models/onnx/gyr66", "models/onnx/pii-engineer"]
    )
    entity_map: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_ONNX_ENTITY_MAP)
    )


@dataclass
class Config:
    strategies: dict[str, str] = field(default_factory=dict)
    dictionary: list[str] = field(default_factory=list)
    detectors: dict[str, bool] = field(default_factory=dict)
    llm: LLMConfig = field(default_factory=LLMConfig)
    onnx: OnnxConfig = field(default_factory=OnnxConfig)
    raw: dict = field(default_factory=dict)

    def strategy_for(self, entity_type: str) -> str:
        return self.strategies.get(
            entity_type, self.strategies.get("DEFAULT", "placeholder")
        )


def load_config(path: str | Path | None = None) -> Config:
    """读配置。相对路径按资源根解析, 与当前工作目录无关; 读不到就报错(两种入口都一样)。

    静默回退到内置默认值等于少一层检测还照样出文件, 所以这里不允许"读不到就算了"——
    不带 `-c` 时默认配置读不到同样是错误, 不能退化成一份空配置(空配置 = 没有引擎被启用,
    在 `docanon engines` 里会显示成"全都配置未启用", 那是误导而不是提示)。
    """
    if path is None:
        cfg_path = resources.config_path("default.yaml")
    else:
        cfg_path = resources.resolve(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    data: dict = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    llm_raw = data.get("llm", {}) or {}
    onnx_raw = data.get("onnx", {}) or {}
    return Config(
        strategies=data.get("strategies", {}) or {},
        dictionary=data.get("dictionary", []) or [],
        detectors=data.get("detectors", {}) or {},
        llm=LLMConfig(
            base_url=llm_raw.get("base_url", LLMConfig.base_url),
            model=llm_raw.get("model", LLMConfig.model),
            timeout=llm_raw.get("timeout", LLMConfig.timeout),
            chunk_size=llm_raw.get("chunk_size", LLMConfig.chunk_size),
            disable_thinking=llm_raw.get("disable_thinking", True),
        ),
        onnx=OnnxConfig(
            model_dirs=onnx_raw.get("model_dirs") or OnnxConfig().model_dirs,
            entity_map=(
                dict(DEFAULT_ONNX_ENTITY_MAP)
                if "entity_map" not in onnx_raw
                else dict(onnx_raw["entity_map"])
            ),
        ),
        raw=data,
    )
