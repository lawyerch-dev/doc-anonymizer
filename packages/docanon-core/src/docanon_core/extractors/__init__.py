"""抽取器包。"""
from docanon_contract import Extractor
from .base import build_extractor, extractor_classes
from docanon_engine_ocr import ImageExtractor
from .pdf import PDFExtractor
from .table import TableExtractor
from .text_file import DocxExtractor, TextFileExtractor
from .legacy_office import LegacyOfficeExtractor

__all__ = [
    "Extractor",
    "build_extractor",
    "extractor_classes",
    "TextFileExtractor",
    "DocxExtractor",
    "PDFExtractor",
    "TableExtractor",
    "LegacyOfficeExtractor",
    "ImageExtractor",
]
