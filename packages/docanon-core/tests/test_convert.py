"""soffice 定位与转换: 用假 soffice 脚本保证离线可测。"""
from __future__ import annotations

from pathlib import Path

import pytest

from docanon_core import convert


def _fake_soffice(tmp_path: Path) -> Path:
    """造一个假 soffice: 把 FIXTURE_DIR/<fmt> 拷成 <src stem>.<fmt>。"""
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    (fixture / "docx").write_bytes(b"PK\x03\x04 fake-docx")
    (fixture / "xlsx").write_bytes(b"PK\x03\x04 fake-xlsx")
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
    return stub


def test_find_soffice_prefers_env(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    assert convert.find_soffice() == stub
    assert convert.unavailable_reason() is None


def test_env_override_wins_even_if_it_is_broken(monkeypatch):
    """显式覆盖就是最终答案: 设了坏路径也不许偷偷回退到系统安装。"""
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/soffice")
    assert convert.find_soffice() is None


def test_find_soffice_none_when_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCANON_SOFFICE", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(convert, "_MAC_SOFFICE", tmp_path / "no.app")
    monkeypatch.setattr("docanon_core.resources.path", lambda key: tmp_path / "absent")
    assert convert.find_soffice() is None
    assert "LibreOffice" in convert.unavailable_reason()


def test_invalid_env_override_is_reported(monkeypatch):
    """坏掉的显式覆盖要暴露路径, 而不是给一句笼统的"缺 LibreOffice"。"""
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    reason = convert.unavailable_reason()
    assert "/no/such/soffice" in reason and "LibreOffice" in reason


def test_to_modern_docx(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "合同.docx"
    assert out.read_bytes().startswith(b"PK")


def test_to_modern_xls_produces_xlsx(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    src = tmp_path / "表.xls"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".xlsx"
    assert out.name == "表.xlsx"


def test_to_modern_rejects_unknown_suffix(tmp_path):
    with pytest.raises(RuntimeError, match="不是可转换"):
        convert.to_modern(tmp_path / "a.txt", tmp_path)


def test_to_modern_missing_soffice_is_a_loud_error(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    with pytest.raises(RuntimeError, match="LibreOffice"):
        convert.to_modern(tmp_path / "a.doc", tmp_path)


def test_non_executable_soffice_counts_as_unavailable(tmp_path, monkeypatch):
    """指向一个不可执行的文件不算"可用" —— 否则会记 error 而不是明确的不可用。"""
    plain = tmp_path / "soffice.txt"
    plain.write_text("not executable\n", encoding="utf-8")
    plain.chmod(0o644)
    monkeypatch.setenv("DOCANON_SOFFICE", str(plain))
    assert convert.find_soffice() is None
    assert convert.unavailable_reason() is not None


def _recording_stub(tmp_path: Path) -> tuple[Path, Path]:
    """记录 argv, 先落一个杂散文件再拷真产物: 同时验 profile 隔离与产物挑选。"""
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    (fixture / "docx").write_bytes(b"PK\x03\x04 fake-docx")
    args_file = tmp_path / "args.txt"
    stub = tmp_path / "soffice"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'echo "$@" >> "$ARGS_FILE"\n'
        'outdir=""; fmt=""\n'
        'while [ $# -gt 0 ]; do case "$1" in\n'
        '  --convert-to) fmt="$2"; shift 2;;\n'
        '  --outdir) outdir="$2"; shift 2;;\n'
        '  *) shift;;\n'
        "esac; done\n"
        ': > "$outdir/stray.tmp"\n'
        'cp "$FIXTURE_DIR/$fmt" "$outdir/out.$fmt"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub, args_file


def test_to_modern_isolates_profile_and_picks_expected_suffix(tmp_path, monkeypatch):
    stub, args_file = _recording_stub(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    monkeypatch.setenv("ARGS_FILE", str(args_file))
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "out.docx", "别把 workdir 里的杂散文件当成产物"
    assert "-env:UserInstallation" in args_file.read_text(encoding="utf-8"), \
        "并发转换必须各自独立 profile, 否则 Web 并发上传会互相抢锁"

