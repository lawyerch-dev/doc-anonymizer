"""抽取器包。"""
from .base import Extractor, build_extractor
from .ocr_image import ImageExtractor
from .pdf import PDFExtractor
from .table import TableExtractor
from .text_file import DocxExtractor, TextFileExtractor

__all__ = [
    "Extractor",
    "build_extractor",
    "TextFileExtractor",
    "DocxExtractor",
    "PDFExtractor",
    "TableExtractor",
    "ImageExtractor",
]
