"""测试用的假 soffice: 把预置的 docx/xlsx 拷成目标名, 让旧格式转换离线可测。

放这里而不是每个测试各写一份: shell 片段和 fixture 造法一旦漂移, 多个测试会一起骗过。
"""
from __future__ import annotations

from pathlib import Path

import openpyxl
from docx import Document


def install_fake_soffice(tmp_path: Path, monkeypatch) -> Path:
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    doc = Document()
    doc.add_paragraph("甲方 张三 手机 13812340000")
    doc.save(str(fixture / "docx"))
    wb = openpyxl.Workbook()
    wb.active["A1"] = "张三 13912345678"
    wb.save(str(fixture / "xlsx"))
    stub = tmp_path / "soffice"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'outdir=""; fmt=""\n'
        'while [ $# -gt 0 ]; do case "$1" in\n'
        '  --convert-to) fmt="$2"; shift 2;;\n'
        '  --outdir) outdir="$2"; shift 2;;\n'
        '  --headless|--norestore) shift;;\n'
        '  *) src="$1"; shift;;\n'
        "esac; done\n"
        'stem="$(basename "$src")"; stem="${stem%.*}"\n'
        'cp "$FIXTURE_DIR/$fmt" "$outdir/$stem.$fmt"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(fixture))
    return fixture
