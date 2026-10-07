"""契约层自身的性质: 它是引擎与 app 唯一的共享面, 形状必须稳定。

契约只依赖标准库(跨包检查在根 tests/test_architecture.py), 这里测的是它给出的语义。
"""
from __future__ import annotations

from docanon_contract import Block, Detection, Engine, ExtractedDoc, Extractor, Span


def test_span_overlaps_touching_edges_do_not_overlap():
    assert Span(0, 3, "abc").overlaps(Span(2, 5, "cde"))
    assert not Span(0, 3, "abc").overlaps(Span(3, 6, "def")), "首尾相接不算重叠"
    assert not Span(3, 6, "def").overlaps(Span(0, 3, "abc"))


def test_block_and_doc_do_not_share_mutable_defaults():
    """dataclass 的 field(default_factory=...) 不能退化成可变默认值。"""
    a, b = Block("b1", "x"), Block("b2", "y")
    a.locator["page"] = 1
    assert b.locator == {}, "两个 Block 共用了同一个 locator 字典"
    d1, d2 = ExtractedDoc("a.txt", []), ExtractedDoc("b.txt", [])
    d1.meta["k"] = 1
    assert d2.meta == {}, "两个 ExtractedDoc 共用了同一个 meta 字典"


def test_detection_defaults():
    det = Detection(Span(0, 2, "张三"), "PERSON", "rule")
    assert det.confidence == 1.0
    assert det.meta == {}


def test_engine_defaults_are_deliberately_blind():
    """基类默认值 = "什么都不认识/没自述": 缺 ready()/capabilities() 的引擎会在清单里露馅。"""

    class Nothing(Engine):
        pass

    e = Nothing()
    assert e.ready() is None
    assert e.capabilities() == []
    assert e.name == "base"


def test_extractor_supports_uses_extensions():
    class Txt(Extractor):
        name = "txt"
        extensions = (".txt",)

        def extract(self, path):
            raise NotImplementedError

    assert Txt().supports(__import__("pathlib").Path("a.TXT")), "后缀比较应该大小写无关"
    assert not Txt().supports(__import__("pathlib").Path("a.md"))
    assert Txt().capabilities() == [".txt"]
