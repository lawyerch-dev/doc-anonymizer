"""图片抽取: 用 RapidOCR 识别文字行, 保留 bbox 供涂黑回写。"""
from __future__ import annotations

from pathlib import Path

from ..models import Block, ExtractedDoc
from ._ocr import run_ocr
from .base import Extractor


class ImageExtractor(Extractor):
    name = "ocr_image"
    extensions = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")

    def extract(self, path: Path) -> ExtractedDoc:
        items = run_ocr(str(path))
        blocks: list[Block] = []
        for idx, item in enumerate(items):
            blocks.append(
                Block(
                    block_id=f"line{idx}",
                    text=item["text"],
                    kind="line",
                    # bbox 用于图片涂黑; score 便于过滤低置信
                    locator={"bbox": item["bbox"], "score": item["score"]},
                )
            )
        return ExtractedDoc(
            source_path=str(path),
            blocks=blocks,
            image_path=str(path),
            meta={"format": "image", "needs_image_redaction": True},
        )
