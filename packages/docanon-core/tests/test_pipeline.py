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
