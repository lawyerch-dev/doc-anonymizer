from docanon_core.detectors.rule import RuleDetector
from docanon_contract import Block, Detection, Span
from docanon_core.redaction.resolve import resolve_overlaps


def test_rule_detects_pii():
    block = Block("b", "联系 13812340000 或 a.b@example.com，身份证 110101199003071234")
    types = {d.entity_type for d in RuleDetector().detect(block)}
    assert "PHONE" in types
    assert "EMAIL" in types
    assert "ID_CARD" in types


def test_rule_detects_landline_passport_and_plate():
    """座机/护照/车牌是实测漏过的三类中文证件(固定电话并入 PHONE)。"""
    block = Block("b", "座机 010-87654321，护照 E12345678，车牌 京A12345。")
    types = {d.entity_type for d in RuleDetector().detect(block)}
    assert {"PHONE", "PASSPORT", "PLATE"} <= types


def test_landline_does_not_eat_digit_runs_inside_codes():
    """全数字的统一社会信用代码里藏得下"0 开头的一串数字", 不许被当成座机。"""
    block = Block("b", "代码 910123456789012345")
    types = {d.entity_type for d in RuleDetector().detect(block)}
    assert "USCC" in types
    assert "PHONE" not in types


def test_new_patterns_stay_quiet_on_ordinary_text():
    block = Block("b", "本次会议共 3 人参加，案卷编号 2024-001，附件共 12 页。")
    assert RuleDetector().detect(block) == []


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
