"""配置加载。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"


@dataclass
class LLMConfig:
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "qwen3.8-4b"
    timeout: int = 120
    chunk_size: int = 1000
    disable_thinking: bool = True


@dataclass
class OnnxConfig:
    model_dirs: list[str] = field(
        default_factory=lambda: ["models/onnx/gyr66", "models/onnx/pii-engineer"]
    )
    entity_map: dict[str, str] | None = None


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
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    data: dict = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
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
            entity_map=onnx_raw.get("entity_map"),
        ),
        raw=data,
    )
