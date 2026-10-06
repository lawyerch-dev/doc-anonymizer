"""引擎契约: 共享数据类型 + 引擎外形(ABC)。

这是可移植的最小共享层 —— 把引擎挪到别的项目时只需要带上这一个文件,
所以它只允许依赖标准库。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Block:
    """抽取器产出的最小文本单元(带定位信息)。"""

    block_id: str
    text: str
    kind: str = "text"  # text | paragraph | cell | page | line
    # 定位信息: 文本文件用 index/paragraph; PDF 用 page; 图片用 bbox
    locator: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    start: int
    end: int
    text: str

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class Detection:
    span: Span
    entity_type: str
    source: str  # rule | dictionary | llm
    confidence: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDoc:
    """一个源文件的抽取结果。"""

    source_path: str
    blocks: list[Block]
    # 若为图片/扫描件: 保存渲染后的图片路径, 用于 bbox 涂黑回写
    image_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class Engine(ABC):
    """抽取器与检测器共同的引擎外形。

    可移植边界就在这个类: 引擎实现只许认识本文件里的类型, 不许 import app 的配置、
    词表或注册表(由 tests/test_architecture.py 用 AST 锁住)。ready()/capabilities()
    是给 `docanon engines` 和跑前预检用的自述, 不是可选装饰。
    """

    name: str = "base"

    def ready(self) -> str | None:
        """开跑前自报健康问题, 返回不可用的原因; None 表示可用。

        少一层引擎就等于少一类脱敏, 所以调用处必须在写任何产物之前问这一次,
        而不是等引擎静默返回空。
        """
        return None

    def capabilities(self) -> list[str]:
        """这个引擎实际能识别什么(实体类型, 或支持的文件扩展名)。"""
        return []


class Detector(Engine, ABC):
    """在一块文本上找敏感片段。"""

    @abstractmethod
    def detect(self, block: Block) -> list[Detection]:
        raise NotImplementedError


class Extractor(Engine, ABC):
    """把一个文件变成带定位信息的文本块。"""

    extensions: tuple[str, ...] = ()

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def capabilities(self) -> list[str]:
        return list(self.extensions)

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDoc:
        raise NotImplementedError
