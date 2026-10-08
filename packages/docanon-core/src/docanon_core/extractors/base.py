"""抽取器注册表。引擎外形(ABC)在 `docanon_contract`。"""
from __future__ import annotations

from pathlib import Path

from docanon_contract import Extractor


def extractor_classes() -> tuple[type[Extractor], ...]:
    """已登记的抽取器类。顺序即路由优先级(PDF 要在通用文本之前)。

    函数而不是模块级常量: 各抽取器会拖进 pypdfium2 / python-docx / RapidOCR,
    import 本模块不该把整条依赖链一起拉进来。
    """
    from docanon_engine_ocr import ImageExtractor
    from .pdf import PDFExtractor
    from .table import TableExtractor
    from .text_file import DocxExtractor, TextFileExtractor
    from .legacy_office import LegacyOfficeExtractor

    return (PDFExtractor, TextFileExtractor, DocxExtractor, TableExtractor,
            LegacyOfficeExtractor, ImageExtractor)


def build_extractor(path: Path, *, allow_legacy: bool = True) -> Extractor:
    """按扩展名返回合适的抽取器。加新抽取器就在上面登记一个类。

    `allow_legacy=False` 时不派发旧格式抽取器, 让 .doc/.xls/.wps 落进调用方的
    "不支持" 兜底桶(对应 config.legacy_convert=false 的旧行为)。
    """
    for cls in extractor_classes():
        if not allow_legacy and cls.name == "legacy_office":
            continue
        extractor = cls()
        if extractor.supports(path):
            return extractor
    raise ValueError(f"不支持的文件类型: {path.suffix or '无扩展名'} ({path})")
