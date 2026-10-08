"""输出布局与 manifest 的行为约定(修同名覆盖 bug)。"""
from __future__ import annotations

import json
from pathlib import Path

from docanon_core.cli import main

SUPPORTED_HINT = "redacted"


def _manifest(out_dir: Path) -> dict:
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def test_same_stem_different_extension_do_not_overwrite(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "名单.txt").write_text("甲文件 张三 13812340000\n", encoding="utf-8")
    (src / "名单.csv").write_text("姓名,手机\n乙文件,13912345678\n", encoding="utf-8")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    assert code == 0
    produced = sorted(p.name for p in out.iterdir() if SUPPORTED_HINT in p.name)
    assert produced == ["名单.csv.redacted.csv", "名单.txt.redacted.txt"]
    assert "乙文件" in (out / "名单.csv.redacted.csv").read_text(encoding="utf-8")
    assert "甲文件" in (out / "名单.txt.redacted.txt").read_text(encoding="utf-8")


def test_same_name_in_different_subdirs_do_not_overwrite(tmp_path):
    (tmp_path / "src" / "a").mkdir(parents=True)
    (tmp_path / "src" / "b").mkdir(parents=True)
    (tmp_path / "src" / "a" / "report.txt").write_text("甲 13812340000\n", encoding="utf-8")
    (tmp_path / "src" / "b" / "report.txt").write_text("乙 13912345678\n", encoding="utf-8")
    out = tmp_path / "out"

    code = main(["run", str(tmp_path / "src"), "-o", str(out)])

    assert code == 0
    assert "138****0000" in (out / "a" / "report.txt.redacted.txt").read_text(encoding="utf-8")
    assert "139****5678" in (out / "b" / "report.txt.redacted.txt").read_text(encoding="utf-8")


def test_single_file_input_keeps_flat_name(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("张三 13812340000\n", encoding="utf-8")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    assert code == 0
    assert "138****0000" in (out / "doc.txt.redacted.txt").read_text(encoding="utf-8")


def test_manifest_lists_unsupported_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "说明.txt").write_text("张三 13812340000\n", encoding="utf-8")
    (src / "归档.zip").write_bytes(b"PK\x03\x04not office")
    (src / ".DS_Store").write_bytes(b"\x00\x01")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entries = {e["source"]: e for e in _manifest(out)["files"]}
    assert entries["说明.txt"]["status"] == "ok"
    assert entries["归档.zip"]["status"] == "unsupported"
    assert ".DS_Store" not in entries, "系统隐藏文件不该进清单"
    assert code != 0, "有文件没被处理时不能报告成功"


def test_manifest_records_extraction_error(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "坏文件.pdf").write_bytes(b"this is not a pdf")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "error"
    assert entry["error"]
    assert code != 0


def test_explicit_unsupported_file_is_reported(tmp_path):
    z = tmp_path / "归档.zip"
    z.write_bytes(b"PK\x03\x04not office")
    out = tmp_path / "out"

    code = main(["run", str(z), "-o", str(out)])

    assert _manifest(out)["files"] == [
        {"source": "归档.zip", "status": "unsupported", "suffix": ".zip"}
    ]
    assert code != 0


def test_doc_converted_and_labelled(tmp_path, monkeypatch):
    from _soffice_stub import install_fake_soffice

    install_fake_soffice(tmp_path, monkeypatch)
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "ok"
    assert entry["source"] == "合同.doc"
    assert entry["source_suffix"] == ".doc"
    assert entry["output_format"] == "docx"
    assert entry["converted"] is True
    assert (out / "合同.doc.redacted.docx").is_file()
    assert code == 0


def test_doc_without_soffice_is_unsupported(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    monkeypatch.setattr("docanon_core.convert.find_soffice", lambda: None)
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "unsupported"
    assert "LibreOffice" in entry.get("reason", "")
    assert code != 0


def test_legacy_convert_off_treats_doc_as_unsupported(tmp_path, monkeypatch):
    """关掉开关就回到旧行为: .doc 一律 unsupported, 连 soffice 都不找。"""
    from _soffice_stub import install_fake_soffice

    install_fake_soffice(tmp_path, monkeypatch)
    (tmp_path / "cfg.yaml").write_text(
        "legacy_convert: false\ndetectors:\n  rule: true\n  dictionary: true\n",
        encoding="utf-8",
    )
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out), "-c", str(tmp_path / "cfg.yaml")])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "unsupported"
    assert entry.get("converted") is None
    assert code != 0


def test_hidden_directories_are_not_treated_as_documents(tmp_path):
    src = tmp_path / "src"
    (src / "docs").mkdir(parents=True)
    (src / ".venv" / "pkg").mkdir(parents=True)
    (src / "docs" / "说明.txt").write_text("张三 13812340000\n", encoding="utf-8")
    (src / ".venv" / "pkg" / "LICENSE.txt").write_text("版权 13812340000\n", encoding="utf-8")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    assert code == 0
    sources = [e["source"] for e in _manifest(out)["files"]]
    assert sources == ["docs/说明.txt"], "隐藏目录(如 .venv)不该被当成文档目录扫描"


def test_manifest_totals_match_entity_counts(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("13812340000 与 13912345678\n", encoding="utf-8")
    (src / "b.txt").write_text("13711112222\n", encoding="utf-8")
    out = tmp_path / "out"

    main(["run", str(src), "-o", str(out)])

    m = _manifest(out)
    assert m["totals"]["PHONE"] == 3
    assert m["summary"] == {"processed": 2, "errors": 0, "unsupported": 0}


def test_second_run_into_same_dir_accumulates(tmp_path):
    """两次 run 进同一个 -o: 清单与映射表累加, 不能把上一次的记录覆盖掉。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "甲.txt").write_text("甲 13812340000\n", encoding="utf-8")
    (src / "乙.txt").write_text("乙 13900001111\n", encoding="utf-8")
    out = tmp_path / "out"

    assert main(["run", str(src / "甲.txt"), "-o", str(out)]) == 0
    assert main(["run", str(src / "乙.txt"), "-o", str(out)]) == 0

    m = _manifest(out)
    assert len(m["files"]) == 2
    assert {e["source"] for e in m["files"]} == {"甲.txt", "乙.txt"}
    assert m["summary"]["processed"] == 2
    assert m["totals"]["PHONE"] == 2
    originals = json.loads((out / "mapping.json").read_text(encoding="utf-8"))["reverse"].values()
    assert {"13812340000", "13900001111"} <= set(originals), "上一次的原文不能被丢掉"


def test_rerun_same_source_replaces_its_entry(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    doc = src / "甲.txt"
    doc.write_text("甲 13812340000\n", encoding="utf-8")
    out = tmp_path / "out"

    assert main(["run", str(doc), "-o", str(out)]) == 0
    doc.write_text("甲 13812340000 乙 13900001111\n", encoding="utf-8")
    assert main(["run", str(doc), "-o", str(out)]) == 0

    m = _manifest(out)
    assert [e["source"] for e in m["files"]] == ["甲.txt"]
    assert m["summary"]["processed"] == 1
    assert m["totals"]["PHONE"] == 2, "重跑同一文件要按最新一次计数, 不能累加成 3"
