"""LLM 检测器: 用本地大模型识别人名/公司/地名等实体。"""
from __future__ import annotations

import json
import re

from ..config import LLMConfig
from ..models import Block, Detection, Span
from ..llm.client import LLMClient
from .base import Detector

_SYSTEM = (
    "你是文档脱敏助手。从给定文本中找出所有敏感实体, 只返回 JSON 数组, "
    '每项形如 {"text": "原文片段", "type": "PERSON|ORG|LOCATION|AMOUNT|SECRET"}。'
    "type 只能是这几种之一。找不到就返回 []。不要输出任何解释。"
)

_VALID_TYPES = {"PERSON", "ORG", "LOCATION", "AMOUNT", "SECRET", "CUSTOM"}


def _extract_json(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


class LLMNERDetector(Detector):
    name = "llm"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.client = LLMClient(config)

    def detect(self, block: Block) -> list[Detection]:
        out: list[Detection] = []
        for chunk in self._chunks(block.text, self.config.chunk_size):
            for item in self._ask(chunk):
                frag = str(item.get("text", "")).strip()
                etype = str(item.get("type", "CUSTOM")).upper()
                if not frag or etype not in _VALID_TYPES:
                    continue
                start = block.text.find(frag)
                while start != -1:
                    out.append(
                        Detection(
                            span=Span(start, start + len(frag), frag),
                            entity_type=etype,
                            source="llm",
                            confidence=0.7,
                        )
                    )
                    start = block.text.find(frag, start + len(frag))
        return out

    def _ask(self, chunk: str) -> list[dict]:
        try:
            reply = self.client.chat(_SYSTEM, chunk)
        except Exception:
            return []
        return _extract_json(reply)

    @staticmethod
    def _chunks(text: str, size: int) -> list[str]:
        if size <= 0 or len(text) <= size:
            return [text]
        return [text[i : i + size] for i in range(0, len(text), size)]
