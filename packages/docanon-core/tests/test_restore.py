"""restore 的边界: remove 策略不可还原, 二进制产物不能还原。

回归点: `remove` 的替换值是空串, 旧实现把它塞进反向表后, `str.replace("", 原文)`
会把原文插到**每个字符之间** —— 还原动作反而把敏感信息撒满全篇(实测过的灾难)。
"""
from __future__ import annotations

import json
import pathlib

from docanon_core.cli import EXIT_INPUT, EXIT_OK, main
from docanon_core.redaction.mapping import MappingStore


def _write_mapping(path: pathlib.Path, reverse: dict[str, str], by_type: dict | None = None) -> None:
    path.write_text(
        json.dumps({"by_type": by_type or {}, "reverse": reverse, "counters": {}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_remove_strategy_never_enters_the_reverse_table():
    store = MappingStore()
    store.get_or_create("SECRET", "sk-abc", lambda n: "")  # remove 策略
    store.get_or_create("PERSON", "张三", lambda n: "林芳")
    assert store.restorable_items() == [("林芳", "张三")]
    assert store.unrestorable_count() == 1


def test_longest_replacement_restored_first():
    store = MappingStore()
    store.get_or_create("PHONE", "13800000000", lambda n: "<PHONE_1>")
    store.get_or_create("CUSTOM", "内部项目代号", lambda n: "X")
    assert store.restorable_items() == [("<PHONE_1>", "13800000000"), ("X", "内部项目代号")]


def test_legacy_mapping_with_empty_key_is_filtered(tmp_path):
    """老 mapping.json 里可能已经躺着空键, 读进来也不能拿去 replace。"""
    p = tmp_path / "mapping.json"
    _write_mapping(p, {"": "sk-abc", "林芳": "张三"})
    store = MappingStore.load(p)
    assert store.restorable_items() == [("林芳", "张三")]
    assert store.unrestorable_count() == 1


def test_restore_does_not_scatter_removed_secrets(tmp_path):
    redacted = tmp_path / "sample.md.redacted.md"
    redacted.write_text("报告: {{PHONE_1}} 与 林芳, 密钥已删除\n", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    _write_mapping(
        mapping,
        {"": "sk-abcdef1234567890", "{{PHONE_1}}": "13800000000", "林芳": "张三"},
        {"SECRET": {"sk-abcdef1234567890": ""}, "PHONE": {"13800000000": "{{PHONE_1}}"}, "PERSON": {"张三": "林芳"}},
    )
    out = tmp_path / "restored.md"

    assert main(["restore", str(redacted), "--mapping", str(mapping), "-o", str(out)]) == EXIT_OK

    assert out.read_text(encoding="utf-8") == "报告: 13800000000 与 张三, 密钥已删除\n"


def test_restore_refuses_pdf_with_a_reason(tmp_path, capsys):
    """pdf 命中页整页栅格化, 原文字层已被删除 —— 明确拒绝, 给出该走哪条路。"""
    src = tmp_path / "【脱敏版】x.pdf"
    src.write_bytes(b"%PDF-1.4\nfake")
    mapping = tmp_path / "mapping.json"
    _write_mapping(mapping, {"{{PERSON_1}}": "张三"})

    assert main(["restore", str(src), "--mapping", str(mapping)]) == EXIT_INPUT
    err = capsys.readouterr().err
    assert "栅格化" in err
    assert "docx" in err  # 告诉他可行的替代路径, 而不是只说做不到


def test_redact_marker_is_never_used_as_a_literal_replacement(tmp_path):
    """`redact` 的替换值是 `**`, 而 markdown 加粗也是 `**`。

    拿 `**` 去全局替换等于把整篇文档的加粗标记换成某个当事人姓名 —— 纯符号替换值
    必须排除在字面替换之外(锚点匹配不受影响)。
    """
    src = tmp_path / "a.md"
    src.write_text("**加粗** 与 **另一处**，共 2 处。\n", encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    _write_mapping(mapping, {"**": "张三"}, {"PERSON": {"张三": "**"}})
    out = tmp_path / "out.md"

    assert main(["restore", str(src), "--mapping", str(mapping), "-o", str(out)]) == EXIT_OK
    assert out.read_text(encoding="utf-8") == "**加粗** 与 **另一处**，共 2 处。\n"


def test_restore_reports_missing_input(tmp_path, capsys):
    mapping = tmp_path / "mapping.json"
    _write_mapping(mapping, {"{{PERSON_1}}": "张三"})
    assert main(["restore", str(tmp_path / "nope.md"), "--mapping", str(mapping)]) == EXIT_INPUT
    assert "不存在" in capsys.readouterr().err


def test_restore_reports_unreadable_mapping(tmp_path, capsys):
    src = tmp_path / "a.md"
    src.write_text("林芳", encoding="utf-8")
    assert main(["restore", str(src), "--mapping", str(tmp_path / "nope.json")]) == EXIT_INPUT
    assert "读不了映射表" in capsys.readouterr().err
