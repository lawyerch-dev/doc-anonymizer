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


def test_bank_card_with_grouping_is_detected():
    """卡号写成 4 位一组(空格或连字符)必须认出来 —— 真实合同/单据基本都是这种写法,
    只认连续数字 = 整类漏抹 = 隐私泄漏。"""
    for text, span in (
        ("账号 6222 0212 3456 7890 123 收", "6222 0212 3456 7890 123"),
        ("账号 6222-0212-3456-7890 收", "6222-0212-3456-7890"),
        ("账号 6222020200001234567 收", "6222020200001234567"),
    ):
        hits = [d for d in RuleDetector().detect(Block("b", text)) if d.entity_type == "BANK_CARD"]
        assert len(hits) == 1, text
        assert hits[0].span.text == span, text


def test_bank_card_grouping_does_not_eat_date_runs():
    """4 位一组的限制值在这里: "2026 03 01 2026 03 01" 是日期串不是卡号。"""
    block = Block("b", "期间 2026 03 01 到 2026 03 01 结束")
    assert [d for d in RuleDetector().detect(block) if d.entity_type == "BANK_CARD"] == []


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
