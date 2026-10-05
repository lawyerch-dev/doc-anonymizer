"""输出布局与 manifest 的行为约定(修同名覆盖 bug)。"""
from __future__ import annotations

import json
from pathlib import Path

from docanon.cli import main

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
    assert produced == ["名单.csv.redacted.txt", "名单.txt.redacted.txt"]
    assert "乙文件" in (out / "名单.csv.redacted.txt").read_text(encoding="utf-8")
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
    (src / "告知书.doc").write_bytes(b"\xd0\xcf\x11\xe0legacy word")
    (src / ".DS_Store").write_bytes(b"\x00\x01")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entries = {e["source"]: e for e in _manifest(out)["files"]}
    assert entries["说明.txt"]["status"] == "ok"
    assert entries["告知书.doc"]["status"] == "unsupported"
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
    doc = tmp_path / "告知书.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0legacy word")
    out = tmp_path / "out"

    code = main(["run", str(doc), "-o", str(out)])

    assert _manifest(out)["files"] == [
        {"source": "告知书.doc", "status": "unsupported", "suffix": ".doc"}
    ]
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
