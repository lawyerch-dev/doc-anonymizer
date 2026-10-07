"""图片抽取: 用 RapidOCR 识别文字行, 保留 bbox 供涂黑回写。

`ocr.py` 是 RapidOCR 引擎的封装, 零包内依赖, 可以整块搬到别的项目里。
"""
from __future__ import annotations

from pathlib import Path

from docanon_contract import Block, ExtractedDoc, Extractor
from .ocr import run_ocr


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
