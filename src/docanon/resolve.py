"""重叠检测结果合并: 保证最终 span 互不重叠, 召回优先。"""
from __future__ import annotations

from .models import Detection

# 来源优先级: 规则/词典 > LLM (规则更精确, 类型更可信)
_SOURCE_RANK = {"rule": 3, "dictionary": 2, "llm": 1}


def resolve_overlaps(detections: list[Detection]) -> list[Detection]:
    """去除重叠, 优选高优先级来源; 同来源取更长的 span。

    采用简单贪心: 按 (来源优先级, 长度) 降序, 依次接受不与已选重叠的项。
    """
    ordered = sorted(
        detections,
        key=lambda d: (
            _SOURCE_RANK.get(d.source, 0),
            d.span.end - d.span.start,
            d.confidence,
        ),
        reverse=True,
    )
    accepted: list[Detection] = []
    for det in ordered:
        if all(not det.span.overlaps(a.span) for a in accepted):
            accepted.append(det)
    return sorted(accepted, key=lambda d: d.span.start)
