"""LLM 检测器: 用本地大模型(OpenAI 兼容端点)识别实体。

与 `docanon/llm/` 合起来就是"本地大模型引擎", 只依赖 `docanon.contract`,
可以整块搬到别的项目里。
"""
from __future__ import annotations

import json
import re

from ..contract import Block, Detection, Detector, Span
from ..llm.client import LLMClient, LLMConfig, LLMError

_SYSTEM = (
    "你是文档脱敏助手。从给定文本中找出所有敏感实体, 只返回 JSON 数组, "
    '每项形如 {"text": "原文片段", "type": "PERSON|ORG|LOCATION|AMOUNT|SECRET"}。'
    "type 只能是这几种之一。找不到就返回 []。不要输出任何解释。"
)

_VALID_TYPES = {"PERSON", "ORG", "LOCATION", "AMOUNT", "SECRET", "CUSTOM"}


def _extract_json(text: str) -> list[dict] | None:
    """返回实体数组; 回答里根本没有 JSON 数组时返回 None(调用处按失败处理)。"""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


class LLMNERDetector(Detector):
    name = "llm"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.client = LLMClient(config)

    def ready(self) -> str | None:
        if self.client.health():
            return None
        return (
            f"{self.config.base_url} 上没有 llama-server 应答"
            "（先跑 ./scripts/serve_llm.sh，或把 detectors.llm_ner 关掉）"
        )

    def capabilities(self) -> list[str]:
        return sorted(_VALID_TYPES)

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
        # chat() 的 LLMError 直接向上抛: 把"没答上"当成"没检出实体"是最坏的失败形态
        reply = self.client.chat(_SYSTEM, chunk)
        data = _extract_json(reply)
        if data is None:
            raise LLMError(f"模型回答里解析不出实体数组: {reply[:80]!r}")
        return data

    @staticmethod
    def _chunks(text: str, size: int) -> list[str]:
        if size <= 0 or len(text) <= size:
            return [text]
        return [text[i : i + size] for i in range(0, len(text), size)]
