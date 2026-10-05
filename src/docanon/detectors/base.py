"""检测器基类与注册表。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Block, Detection


class Detector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, block: Block) -> list[Detection]:
        """在单个文本块上检测敏感信息。"""
        raise NotImplementedError


def build_detectors(config) -> list[Detector]:
    """按配置构建启用的检测器。"""
    from .dictionary import DictionaryDetector
    from .llm_ner import LLMNERDetector
    from .rule import RuleDetector

    enabled = config.detectors or {}
    detectors: list[Detector] = []
    if enabled.get("rule", True):
        detectors.append(RuleDetector())
    if enabled.get("dictionary", True):
        detectors.append(DictionaryDetector(config.dictionary))
    if enabled.get("llm_ner", False):
        detectors.append(LLMNERDetector(config.llm))
    return detectors
