"""抽取器包。"""
from ..contract import Extractor
from .base import build_extractor, extractor_classes
from ..engines.ocr_image import ImageExtractor
from .pdf import PDFExtractor
from .table import TableExtractor
from .text_file import DocxExtractor, TextFileExtractor

__all__ = [
    "Extractor",
    "build_extractor",
    "extractor_classes",
    "TextFileExtractor",
    "DocxExtractor",
    "PDFExtractor",
    "TableExtractor",
    "ImageExtractor",
]
