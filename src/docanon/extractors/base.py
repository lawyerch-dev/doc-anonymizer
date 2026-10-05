"""抽取器基类与注册表。按文件类型选择抽取器。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ExtractedDoc


class Extractor(ABC):
    name: str = "base"
    extensions: tuple[str, ...] = ()

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDoc:
        raise NotImplementedError


def build_extractor(path: Path) -> Extractor:
    """根据扩展名返回合适的抽取器。"""
    from .ocr_image import ImageExtractor
    from .pdf import PDFExtractor
    from .table import TableExtractor
    from .text_file import DocxExtractor, TextFileExtractor

    for cls in (PDFExtractor, TextFileExtractor, DocxExtractor, TableExtractor, ImageExtractor):
        extractor = cls()
        if extractor.supports(path):
            return extractor
    raise ValueError(f"不支持的文件类型: {path.suffix} ({path})")
