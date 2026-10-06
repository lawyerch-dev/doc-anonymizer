from docanon.detectors.rule import RuleDetector
from docanon.contract import Block, Detection, Span
from docanon.resolve import resolve_overlaps


def test_rule_detects_pii():
    block = Block("b", "联系 13812340000 或 a.b@example.com，身份证 110101199003071234")
    types = {d.entity_type for d in RuleDetector().detect(block)}
    assert "PHONE" in types
    assert "EMAIL" in types
    assert "ID_CARD" in types


def test_resolve_prefers_rule_over_llm():
    rule = Detection(Span(0, 11, "13812340000"), "PHONE", "rule")
    llm = Detection(Span(0, 11, "13812340000"), "AMOUNT", "llm")
    out = resolve_overlaps([llm, rule])
    assert len(out) == 1
    assert out[0].entity_type == "PHONE"


def test_resolve_drops_overlapping_shorter():
    a = Detection(Span(0, 18, "x" * 18), "ID_CARD", "rule")
    b = Detection(Span(0, 18, "x" * 18), "BANK_CARD", "rule")
    out = resolve_overlaps([a, b])
    assert len(out) == 1
