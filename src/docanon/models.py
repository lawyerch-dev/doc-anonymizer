"""核心数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Block:
    """抽取器产出的最小文本单元(带定位信息)。"""

    block_id: str
    text: str
    kind: str = "text"  # text | paragraph | cell | page | line
    # 定位信息: 文本文件用 index/paragraph; PDF 用 page; 图片用 bbox
    locator: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    start: int
    end: int
    text: str

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class Detection:
    span: Span
    entity_type: str
    source: str  # rule | dictionary | llm
    confidence: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDoc:
    """一个源文件的抽取结果。"""

    source_path: str
    blocks: list[Block]
    # 若为图片/扫描件: 保存渲染后的图片路径, 用于 bbox 涂黑回写
    image_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
