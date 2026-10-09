from pathlib import Path

from docanon_core.config import load_config
from docanon_core.redaction.mapping import MappingStore
from docanon_core.pipeline import process_file


def _run(tmp_path: Path, text: str):
    doc = tmp_path / "a.txt"
    doc.write_text(text, encoding="utf-8")
    cfg = load_config()
    store = MappingStore()
    res = process_file(doc, tmp_path, cfg, store)
    out = Path(res.output_path).read_text(encoding="utf-8")
    return res, out, store


def test_pipeline_masks_pii(tmp_path):
    res, out, _ = _run(
        tmp_path, "张三手机 13812340000，邮箱 a.b@example.com，身份证 110101199003071234"
    )
    assert "13812340000" not in out
    assert "a.b@example.com" not in out
    assert "110101199003071234" not in out
    assert res.entity_counts.get("PHONE") == 1
    assert res.entity_counts.get("EMAIL") == 1


def test_pseudonym_is_consistent_via_store(tmp_path):
    # PERSON 由 LLM 检测器产生; 这里直接验证策略层的一致性
    from docanon_core.redaction.strategies import replacement_for

    store = MappingStore()
    a = replacement_for(store, "PERSON", "张三", "pseudonym")
    b = replacement_for(store, "PERSON", "张三", "pseudonym")
    c = replacement_for(store, "PERSON", "李四", "pseudonym")
    assert a == b
    assert a != c
    assert "张三" not in a


def test_redact_strategy_is_a_flat_marker():
    """redact = 用 ** 整体盖掉原文, 绝不产出像真的内容(这是默认口径)。"""
    from docanon_core.redaction.strategies import replacement_for

    store = MappingStore()
    assert replacement_for(store, "PERSON", "张三", "redact") == "**"
    assert replacement_for(store, "ORG", "北京华信科技有限公司", "redact") == "**"


def test_default_and_onnx_configs_do_not_fake_names():
    """默认配置交付的必须是 ** 而不是可信的假名/假公司, 免得用户以为没脱敏。"""
    from docanon_core.config import load_config

    for cfg_name in (None, "configs/onnx.yaml", "configs/llm.yaml"):
        cfg = load_config(cfg_name)
        for entity in ("PERSON", "ORG", "CUSTOM", "DEFAULT"):
            assert cfg.strategy_for(entity) == "redact", (cfg_name, entity, cfg.strategy_for(entity))



def test_dictionary_custom_detected(tmp_path):
    _, out, _ = _run(tmp_path, "公司是内部项目代号X，请勿外传。")
    # 词典命中 CUSTOM 并被替换
    assert out.count("内部项目代号") == 0 or "CUSTOM" in out


def test_mapping_restore_roundtrip(tmp_path):
    text = "手机 13812340000"
    _, out, store = _run(tmp_path, text)
    for repl, original in store._reverse.items():
        out = out.replace(repl, original)
    assert "13812340000" in out


def _stub(source: str, frag: str):
    """只认一个片段的假检测器, 用来单独验合并/取舍, 不惊动真模型。"""
    from docanon_contract import Detection, Span

    class _D:
        name = source

        def detect(self, block):
            start = block.text.find(frag)
            if start < 0:
                return []
            return [Detection(span=Span(start, start + len(frag), frag),
                              entity_type="ORG", source=source)]

    return _D()


def _block(text: str):
    from docanon_contract import Block

    return Block(block_id="b0", text=text, locator={"line": 0})


def test_quoted_titles_are_not_redacted_by_model_layers():
    """《》里是法规/文件名, 模型层把它当机构抹掉会把文件抹废(实测: 《民法典》->《**》)。"""
    from docanon_core.pipeline import _detect_block

    text = "依据《中华人民共和国民法典》及相关法规, 联系人张三。"
    assert _detect_block(_block(text), [_stub("llm", "中华人民共和国民法典")]) == []
    assert _detect_block(_block(text), [_stub("onnx", "民法典")]) == []


def test_quoted_title_guard_does_not_cover_rule_or_dictionary():
    """规则/词典是精确匹配(用户明确列的词、写死的号码格式) —— 不该被书名号护栏放过。"""
    from docanon_core.pipeline import _detect_block

    text = "依据《民法典》办理。"
    assert len(_detect_block(_block(text), [_stub("dictionary", "民法典")])) == 1
    assert len(_detect_block(_block(text), [_stub("rule", "民法典")])) == 1


def test_model_layers_still_catch_what_is_outside_the_quotes():
    from docanon_core.pipeline import _detect_block

    got = _detect_block(_block("依据《民法典》, 联系人张三。"), [_stub("llm", "张三")])
    assert [d.span.text for d in got] == ["张三"]


def test_amount_without_money_marks_is_not_an_amount():
    """AMOUNT 必须有"钱的痕迹" —— 实测期限"十日"被模型当金额抹掉, 合同期限就没了。"""
    from docanon_contract import Detection, Span
    from docanon_core.pipeline import _detect_block

    def stub(source: str, frag: str, etype: str):
        class _D:
            name = source

            def detect(self, block):
                start = block.text.find(frag)
                return [] if start < 0 else [
                    Detection(span=Span(start, start + len(frag), frag),
                              entity_type=etype, source=source)
                ]

        return _D()

    text = "按总费用的1%支付违约金, 逾期超过十日的, 甲方可解除。"
    # 模型层: "十日"没有钱的痕迹 -> 丢; "1%" 有钱的痕迹 -> 留
    assert [d.span.text for d in _detect_block(_block(text), [stub("llm", "十日", "AMOUNT")])] == []
    assert [d.span.text for d in _detect_block(_block(text), [stub("llm", "1%", "AMOUNT")])] == ["1%"]
    # 规则层是精确匹配, 不受这条限制
    assert [d.span.text for d in _detect_block(_block(text), [stub("rule", "十日", "AMOUNT")])] == ["十日"]
