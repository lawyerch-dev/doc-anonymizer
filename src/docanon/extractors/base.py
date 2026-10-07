"""抽取器注册表。引擎外形(ABC)在 `docanon.contract`。"""
from __future__ import annotations

from pathlib import Path

from ..contract import Extractor


def extractor_classes() -> tuple[type[Extractor], ...]:
    """已登记的抽取器类。顺序即路由优先级(PDF 要在通用文本之前)。

    函数而不是模块级常量: 各抽取器会拖进 pypdfium2 / python-docx / RapidOCR,
    import 本模块不该把整条依赖链一起拉进来。
    """
    from ..engines.ocr_image import ImageExtractor
    from .pdf import PDFExtractor
    from .table import TableExtractor
    from .text_file import DocxExtractor, TextFileExtractor

    return (PDFExtractor, TextFileExtractor, DocxExtractor, TableExtractor, ImageExtractor)


def build_extractor(path: Path) -> Extractor:
    """按扩展名返回合适的抽取器。加新抽取器就在上面登记一个类。"""
    for cls in extractor_classes():
        extractor = cls()
        if extractor.supports(path):
            return extractor
    raise ValueError(f"不支持的文件类型: {path.suffix or '无扩展名'} ({path})")
