"""docanon-engine-ocr: RapidOCR 引擎(图片/扫描页 → 文字 + bbox)。

只依赖 docanon-contract 与第三方推理库, 不 import app(core) 与另一个引擎。
"整块搬走"由 tests/test_engine_portability.py 真跑验证。
"""
from .image import ImageExtractor
from .ocr import run_ocr

__all__ = ["ImageExtractor", "run_ocr"]
