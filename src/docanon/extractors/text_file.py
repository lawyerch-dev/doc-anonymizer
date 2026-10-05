"""文字类文档抽取: TXT / MD / DOCX。"""
from __future__ import annotations

from pathlib import Path

from ..models import Block, ExtractedDoc
from .base import Extractor


class TextFileExtractor(Extractor):
    name = "text_file"
    extensions = (".txt", ".md", ".markdown", ".text")

    def extract(self, path: Path) -> ExtractedDoc:
        text = path.read_text(encoding="utf-8", errors="replace")
        # 按段落切块, 便于定位与增量处理
        blocks: list[Block] = []
        for idx, para in enumerate(text.split("\n")):
            if para.strip() == "":
                continue
            blocks.append(
                Block(
                    block_id=f"p{idx}",
                    text=para,
                    kind="paragraph",
                    locator={"line": idx},
                )
            )
        return ExtractedDoc(source_path=str(path), blocks=blocks, meta={"format": "text"})


class DocxExtractor(Extractor):
    name = "docx"
    extensions = (".docx",)

    def extract(self, path: Path) -> ExtractedDoc:
        from docx import Document  # python-docx

        doc = Document(str(path))
        blocks: list[Block] = []
        for idx, para in enumerate(doc.paragraphs):
            if not para.text.strip():
                continue
            blocks.append(
                Block(
                    block_id=f"p{idx}",
                    text=para.text,
                    kind="paragraph",
                    locator={"paragraph": idx},
                )
            )
        return ExtractedDoc(source_path=str(path), blocks=blocks, meta={"format": "docx"})
