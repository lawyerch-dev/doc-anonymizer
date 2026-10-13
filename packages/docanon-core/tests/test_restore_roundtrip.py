"""「脱敏 → 交 AI → 还原」闭环的锁定测试。

这里守的是四件事, 每一件都对应一种真实的翻车方式:

1. **跨 run 还原** —— 锚点被 Word/AI 拆到多个 run 里(拼写检查、格式刷、往返转换都会拆)。
   逐 run 各自替换会一个都匹配不上, 必须先拼整段再把 span 映射回各 run。
2. **样式零改动** —— 只碰 `run.text`, 字体/字号/颜色/下划线必须原样。
   一旦改成"读成纯文本再重建", 这些属性就全没了, 而用户要的就是原格式。
3. **重排免疫** —— 定位靠锚点文本, 不靠段落序号。AI 会重排段落, 位置信息必然失效。
4. **漏还原要报** —— AI 删掉或改坏锚点时必须报出来并给非零退出码。
   静默少还原等于交出一份"看着还原了、其实少了几处"的文件, 比不还原更危险。
"""
from __future__ import annotations

import json
import pathlib

import pytest
from docx import Document
from docx.shared import Pt, RGBColor

from docanon_core.cli import EXIT_INPUT, EXIT_OK, EXIT_PARTIAL, main
from docanon_core.redaction.restorers import (
    RestoreError,
    is_anchor,
    restore_file,
)
from docanon_core.redaction.strategies import (
    irreversible_types,
    make_replacer,
)

REVERSE = {
    "{{PERSON_1}}": "陈某某",
    "{{PERSON_2}}": "王某某",
    "{{PHONE_1}}": "13812345678",
    "{{ORG_1}}": "某某建筑有限公司",
}
TABLE = {"{{PERSON_1}}": "陈某某", "{{PERSON_2}}": "王某某",
         "{{PHONE_1}}": "13812345678", "{{ORG_1}}": "某某建筑有限公司"}


def _write_mapping(path: pathlib.Path, reverse: dict[str, str] | None = None) -> pathlib.Path:
    reverse = REVERSE if reverse is None else reverse
    path.write_text(
        json.dumps(
            {"by_type": {}, "reverse": reverse, "counters": {}, "uses": {}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _styled_docx(path: pathlib.Path, texts: list[str]) -> pathlib.Path:
    """造一个每段带独特样式的 docx, 便于断言样式没被动过。"""
    d = Document()
    for i, text in enumerate(texts):
        p = d.add_paragraph()
        r = p.add_run(text)
        r.font.bold = True
        r.font.size = Pt(12 + i)
        r.font.name = "SimSun"
        r.font.color.rgb = RGBColor(0xC7, 0x00, 0x0B)
        r.font.underline = True
    d.save(str(path))
    return path


def _style_of(path: pathlib.Path, idx: int = 0):
    r = Document(str(path)).paragraphs[idx].runs[0]
    color = r.font.color.rgb if r.font.color and r.font.color.type else None
    return (r.font.bold, r.font.size, r.font.name, str(color), r.font.underline)


# ------------------------------------------------------------------ 策略

def test_anchor_strategy_emits_braced_token():
    assert make_replacer("PERSON", "anchor")(1, "张三") == "{{PERSON_1}}"


def test_anchor_uses_double_braces_not_angle_brackets():
    """单尖括号会被 HTML/markdown 当语法: `<P_1>` 会被转义或被模板引擎吞掉。"""
    out = make_replacer("PERSON", "anchor")(3, "张三")
    assert "<" not in out and ">" not in out
    assert out == "{{PERSON_3}}"


def test_is_anchor_recognises_both_generations():
    assert is_anchor("{{PERSON_1}}")       # 新 anchor 策略
    assert is_anchor("<PERSON_1>")         # 老 placeholder 策略产出的历史 mapping
    assert not is_anchor("138****5678")    # mask: 不可还原, 不该进对账账本
    assert not is_anchor("**")             # redact
    assert not is_anchor("")


def test_irreversible_strategies_are_reported_from_config():
    from docanon_core.config import config_from_dict

    cfg = config_from_dict({"strategies": {"PHONE": "mask", "PERSON": "keep", "ORG": "anchor"}})
    # 只报会被兜住的: mask 命中; keep 不是替换; anchor 可还原故不报
    assert irreversible_types(cfg) == {"PHONE": "mask"}

    defaulted = config_from_dict({"strategies": {"DEFAULT": "redact"}})
    assert "其余全部类型" in "".join(irreversible_types(defaulted))


# ------------------------------------------------------------------ docx 还原

def test_docx_restore_keeps_every_style_attribute(tmp_path):
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{PERSON_1}}，电话 {{PHONE_1}}。"])
    before = _style_of(src)
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE)

    assert res.total_restored == 2
    assert Document(str(out)).paragraphs[0].text == "原告 陈某某，电话 13812345678。"
    assert _style_of(out) == before


def test_docx_restore_handles_anchor_split_across_runs(tmp_path):
    """锚点被拆到 3 个 run: 逐 run 替换必然一个都匹配不上。"""
    src = tmp_path / "split.docx"
    d = Document()
    p = d.add_paragraph()
    a = p.add_run("原告 "); a.font.bold = True; a.font.color.rgb = RGBColor(0xC7, 0, 0x0B)
    b = p.add_run("{{PER"); b.italic = True; b.font.size = Pt(9)
    c = p.add_run("SON_1}}，住"); c.font.size = Pt(9)
    e = p.add_run("址 {{PHONE_1}}。"); e.font.underline = True
    d.save(str(src))
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE)

    assert res.total_restored == 2
    doc = Document(str(out))
    assert doc.paragraphs[0].text == "原告 陈某某，住址 13812345678。"
    # 起点 run 的样式保住, 被覆盖掉的后续 run 只清掉重叠部分
    assert doc.paragraphs[0].runs[0].font.bold is True
    assert str(doc.paragraphs[0].runs[0].font.color.rgb) == "C7000B"


def test_docx_restore_survives_paragraph_reordering(tmp_path):
    """定位靠锚点文本而非段落序号 —— AI 重排后还原依然正确。"""
    src = _styled_docx(tmp_path / "in.docx", ["电话 {{PHONE_1}}", "原告 {{PERSON_1}}"])
    # 模拟 AI 把第一段挪到最后
    d = Document(str(src))
    body = d.element.body
    ps = [p for p in body.iterchildren() if p.tag.endswith("}p")]
    body.remove(ps[0])
    body.append(ps[0])
    d.save(str(src))
    out = tmp_path / "out.docx"

    restore_file(src, out, REVERSE)

    texts = [p.text for p in Document(str(out)).paragraphs if p.text.strip()]
    assert texts == ["原告 陈某某", "电话 13812345678"]


def test_docx_restore_tolerates_ai_whitespace_and_case_changes(tmp_path):
    """AI 可能加空格、改大小写 —— 这些是"同一个锚点被包了一层", 不是还原失败。"""
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{ person_1 }}，电话 {{PHONE_1}}。"])
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE)

    assert res.total_restored == 2
    assert Document(str(out)).paragraphs[0].text == "原告 陈某某，电话 13812345678。"


def test_docx_restore_reports_anchors_ai_deleted(tmp_path):
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{PERSON_1}}。"])
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE, expected={"{{PERSON_1}}": 1, "{{ORG_1}}": 2})

    assert res.missing == ["{{ORG_1}}"]
    assert not res.complete
    # 少还原的部分要真留在文档里, 不能被悄悄填成别的原文
    assert Document(str(out)).paragraphs[0].text == "原告 陈某某。"


def test_unknown_anchor_is_never_guessed(tmp_path):
    """AI 幻觉出的 {{PERSON_99}} 若被当成真锚点, 等于把无关人名插进正文。"""
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{PERSON_99}} 与 {{PERSON_1}}。"])
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE)

    assert res.unknown == ["{{PERSON_99}}"]
    assert Document(str(out)).paragraphs[0].text == "原告 {{PERSON_99}} 与 陈某某。"


def test_pdf_is_refused_with_an_actionable_reason(tmp_path):
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(RestoreError) as exc:
        restore_file(src, tmp_path / "o.pdf", REVERSE)
    assert "栅格化" in str(exc.value)
    assert "docx" in str(exc.value)   # 必须给出可行的替代路径


def test_docx_without_anchors_is_copied_byte_for_byte(tmp_path):
    """一个锚点都没有时不要让 python-docx 重写文件: 它会丢掉自己不认识的部件。"""
    src = tmp_path / "clean.docx"
    _styled_docx(src, ["本文不含任何敏感信息。"])
    original = src.read_bytes()
    out = tmp_path / "out.docx"

    res = restore_file(src, out, REVERSE)

    assert res.total_restored == 0
    assert out.read_bytes() == original


# ------------------------------------------------------------------ 表格

def test_xlsx_restore_replaces_cells_and_keeps_sheet_structure(tmp_path):
    from openpyxl import Workbook, load_workbook

    src = tmp_path / "in.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "当事人"
    ws["A1"] = "姓名"
    ws["B1"] = "{{PERSON_1}}"
    ws["A2"] = "电话"
    ws["B2"] = "{{PHONE_1}}"
    from copy import copy

    bold = copy(ws["B1"].font)
    bold.bold = True
    ws["B1"].font = bold
    wb.save(str(src))
    out = tmp_path / "out.xlsx"

    res = restore_file(src, out, REVERSE)

    got = load_workbook(str(out))
    assert res.total_restored == 2
    assert got["当事人"]["B1"].value == "陈某某"
    assert got["当事人"]["B2"].value == "13812345678"
    assert got["当事人"]["A1"].value == "姓名"  # 表结构没被动


# ------------------------------------------------------------------ 文本

def test_text_restore_reports_both_kinds_of_gap(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("原告 {{PERSON_1}} 与 {{PERSON_77}}。\n", encoding="utf-8")
    out = tmp_path / "out.md"

    res = restore_file(src, out, REVERSE, expected={"{{PERSON_1}}": 1, "{{ORG_1}}": 1})

    assert res.restored == {"{{PERSON_1}}": 1}
    assert res.unknown == ["{{PERSON_77}}"]
    assert res.missing == ["{{ORG_1}}"]


def test_csv_restore_keeps_row_and_column_count(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("姓名,电话\n{{PERSON_1}},{{PHONE_1}}\n张三,138\n", encoding="utf-8")
    out = tmp_path / "out.csv"

    res = restore_file(src, out, REVERSE)

    lines = out.read_text(encoding="utf-8-sig").strip().split("\n")
    assert res.total_restored == 2
    assert lines[1] == "陈某某,13812345678"
    assert len(lines) == 3   # 行数没变


# ------------------------------------------------------------------ CLI 契约

def test_cli_restore_exit_code_two_on_incomplete(tmp_path, capsys):
    src = _styled_docx(tmp_path / "in.docx", ["只有 {{PERSON_1}}。"])
    mapping = _write_mapping(tmp_path / "mapping.json")
    out = tmp_path / "out.docx"

    code = main([
        "restore", str(src), "--mapping", str(mapping), "-o", str(out),
        "--expected", '{"{{ORG_1}}": 1}',
    ])

    assert code == EXIT_PARTIAL
    err = capsys.readouterr().err
    assert "{{ORG_1}}" in err


def test_cli_restore_writes_a_json_report(tmp_path):
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{PERSON_1}}。"])
    mapping = _write_mapping(tmp_path / "mapping.json")
    report = tmp_path / "report.json"

    code = main([
        "restore", str(src), "--mapping", str(mapping),
        "-o", str(tmp_path / "o.docx"), "--report", str(report),
    ])

    data = json.loads(report.read_text(encoding="utf-8"))
    assert code == EXIT_OK
    assert data["total_restored"] == 1
    assert data["complete"] is True
    assert data["restored"] == {"{{PERSON_1}}": 1}


def test_cli_default_output_replaces_the_redaction_prefix(tmp_path):
    """默认产物名是替换而不是叠加 —— 否则会得到 【还原版】【脱敏版】x.docx。"""
    src = _styled_docx(tmp_path / "【脱敏版】x.docx", ["原告 {{PERSON_1}}。"])
    mapping = _write_mapping(tmp_path / "mapping.json")

    code = main(["restore", str(src), "--mapping", str(mapping)])

    assert code == EXIT_OK
    assert (tmp_path / "【还原版】x.docx").exists()


def test_cli_accepts_manifest_path_as_expected(tmp_path):
    """手工写几十个锚点的 JSON 太啰嗦, 而 manifest 里本来就记着。"""
    src = _styled_docx(tmp_path / "in.docx", ["原告 {{PERSON_1}}。"])
    mapping = _write_mapping(tmp_path / "mapping.json")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "files": [
            {"source": "a.docx", "anchors": {"{{PERSON_1}}": 1}},
            {"source": "b.docx", "anchors": {"{{ORG_1}}": 1}},
        ]
    }), encoding="utf-8")

    # 两个文件都带 anchors -> 说不清是哪个, 应当拒绝而不是猜
    with pytest.raises(SystemExit):
        main(["restore", str(src), "--mapping", str(mapping),
              "--expected", str(manifest), "-o", str(tmp_path / "o.docx")])


def test_cli_rejects_pdf_with_exit_code_one(tmp_path, capsys):
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    mapping = _write_mapping(tmp_path / "mapping.json")

    assert main(["restore", str(src), "--mapping", str(mapping)]) == EXIT_INPUT
    assert "还原失败" in capsys.readouterr().err