"""自定义业务敏感词检测器。"""
from __future__ import annotations

from ..contract import Block, Detection, Detector, Span


class DictionaryDetector(Detector):
    name = "dictionary"

    def capabilities(self) -> list[str]:
        return ["CUSTOM"]

    def __init__(self, words: list[str]) -> None:
        # 去掉空词并长词优先, 保证较长敏感词先匹配
        self.words = sorted({w for w in (words or []) if w}, key=len, reverse=True)

    def detect(self, block: Block) -> list[Detection]:
        out: list[Detection] = []
        text = block.text
        for word in self.words:
            start = text.find(word)
            while start != -1:
                out.append(
                    Detection(
                        span=Span(start, start + len(word), word),
                        entity_type="CUSTOM",
                        source="dictionary",
                        confidence=1.0,
                    )
                )
                start = text.find(word, start + len(word))
        return out
