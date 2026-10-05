"""PDF 抽取: 优先文字层; 无文字层的页(扫描件)渲染后用 OCR。"""
from __future__ import annotations

from pathlib import Path

from ..models import Block, ExtractedDoc
from .base import Extractor

_MIN_TEXT_CHARS = 8  # 少于此字符数视为该页无可用文字层


class PDFExtractor(Extractor):
    name = "pdf"
    extensions = (".pdf",)

    def extract(self, path: Path) -> ExtractedDoc:
        import pypdfium2 as pdfium

        from ._ocr import run_ocr

        pdf = pdfium.PdfDocument(str(path))
        blocks: list[Block] = []
        scanned_pages: list[dict] = []

        for pno in range(len(pdf)):
            page = pdf[pno]
            textpage = page.get_textpage()
            text = (textpage.get_text_range() or "").strip()

            if len(text) >= _MIN_TEXT_CHARS:
                blocks.append(
                    Block(
                        block_id=f"page{pno}",
                        text=text,
                        kind="page",
                        locator={"page": pno},
                    )
                )
            else:
                # 扫描页: 渲染为图片并 OCR
                bitmap = page.render(scale=2.0)
                pil = bitmap.to_pil()
                items = run_ocr(pil)
                for idx, item in enumerate(items):
                    blocks.append(
                        Block(
                            block_id=f"page{pno}_line{idx}",
                            text=item["text"],
                            kind="line",
                            locator={"page": pno, "bbox": item["bbox"]},
                        )
                    )
                scanned_pages.append({"page": pno, "image": pil})

        meta: dict = {"format": "pdf", "scanned_pages": [p["page"] for p in scanned_pages]}
        doc = ExtractedDoc(source_path=str(path), blocks=blocks, meta=meta)
        if scanned_pages:
            doc.meta["needs_image_redaction"] = True
            doc.meta["_scanned_images"] = scanned_pages  # 供回写使用
        return doc
