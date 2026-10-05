"""RapidOCR 封装: 兼容 rapidocr 1.x/2.x, 输出统一的 (bbox, text, score)。"""
from __future__ import annotations

from typing import Any

_engine = None


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:  # 2.x
        from rapidocr import RapidOCR  # type: ignore

        _engine = RapidOCR()
        return _engine
    except Exception:
        pass
    try:  # 1.x
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        _engine = RapidOCR()
        return _engine
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 RapidOCR。请执行: pip install -e '.[ocr]'"
        ) from exc


def _bbox(points: Any) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def run_ocr(image: Any) -> list[dict]:
    """返回 [{"bbox": (x0,y0,x1,y1), "text": str, "score": float}]。"""
    engine = _get_engine()
    result = engine(image)

    items: list[dict] = []
    # 2.x: 对象带 .boxes/.txts/.scores
    if hasattr(result, "boxes") and getattr(result, "boxes", None) is not None:
        boxes = result.boxes
        txts = result.txts
        scores = result.scores
        for i in range(len(txts)):
            items.append(
                {"bbox": _bbox(boxes[i]), "text": str(txts[i]), "score": float(scores[i])}
            )
        return items

    # 1.x: (list[[box, text, score]], elapse)
    raw = result[0] if isinstance(result, tuple) else result
    if not raw:
        return []
    for box, text, score in raw:
        items.append({"bbox": _bbox(box), "text": str(text), "score": float(score)})
    return items
