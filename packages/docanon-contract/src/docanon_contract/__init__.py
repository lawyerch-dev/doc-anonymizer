"""docanon-contract: 引擎与 app 之间唯一的共享层。

只依赖标准库 —— 这是"引擎能整块搬走"的前提, 由 tests/test_architecture.py 锁死。
"""
from .contract import (
    Block,
    Detection,
    Detector,
    Engine,
    ExtractedDoc,
    Extractor,
    Span,
)

__all__ = ["Block", "Detection", "Detector", "Engine", "ExtractedDoc", "Extractor", "Span"]
