"""脱敏层: 策略替换 + 全局映射(一致性/可还原) + 重叠合并 + 原格式回写。"""
from .mapping import MappingStore
from .resolve import resolve_overlaps
from .strategies import apply_spans, make_replacer, replacement_for
from .writers import BlockRedaction, write_output

__all__ = [
    "MappingStore",
    "BlockRedaction",
    "apply_spans",
    "make_replacer",
    "replacement_for",
    "resolve_overlaps",
    "write_output",
]
