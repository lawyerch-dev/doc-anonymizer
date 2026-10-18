"""soffice 定位与转换: 用假 soffice 脚本保证离线可测。"""
from __future__ import annotations

from pathlib import Path

import pytest

from docanon_core import convert
from _soffice_stub import install_fake_soffice


def test_find_soffice_prefers_env(tmp_path, monkeypatch):
    install_fake_soffice(tmp_path, monkeypatch, real_documents=False)
    assert convert.find_soffice() == tmp_path / "soffice"
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
    install_fake_soffice(tmp_path, monkeypatch, real_documents=False)
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "合同.docx"
    assert out.read_bytes().startswith(b"PK")


def test_to_modern_xls_produces_xlsx(tmp_path, monkeypatch):
    install_fake_soffice(tmp_path, monkeypatch, real_documents=False)
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


def test_to_modern_isolates_profile_and_picks_expected_suffix(tmp_path, monkeypatch):
    """产物另起了名字 + 同目录还有杂散文件时, 仍要挑到真产物; 并发转换要各自独立 profile。"""
    args_file = tmp_path / "args.txt"
    install_fake_soffice(
        tmp_path, monkeypatch,
        real_documents=False, record_args=args_file, output_mode="other",
    )
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "out.docx", "别把 workdir 里的杂散文件当成产物"
    assert "-env:UserInstallation" in args_file.read_text(encoding="utf-8"), \
        "并发转换必须各自独立 profile, 否则 Web 并发上传会互相抢锁"


def test_multiple_products_prefer_the_one_named_after_the_source(tmp_path, monkeypatch):
    """同名冲突时 soffice 会另起 `<名> 1.docx`; 挑哪个不许靠 glob 顺序。

    命名只由输入决定(与 `_output_path` 同一条纪律): 同一份输入每次都该挑到同一个产物,
    否则账本里记的路径会随文件系统枚举顺序漂。
    """
    install_fake_soffice(tmp_path, monkeypatch, real_documents=False, output_mode="both")
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "合同.docx", "同目录里另有 out.docx 时, 必须优先源名一致的那个"


# ---- Windows 分支: 在 mac 上靠 _IS_WINDOWS 开关与假目录验(与 _MAC_SOFFICE 的 monkeypatch 同一手法) ----

def _bundled_tree(tmp_path, monkeypatch, *names: str) -> Path:
    """造一棵 var/libreoffice/program, 并把 PATH 与固定安装位都挡掉 —— 让 find_soffice 只看这棵树。"""
    program = tmp_path / "libreoffice" / "program"
    program.mkdir(parents=True)
    for name in names:
        p = program / name
        p.write_bytes(b"#!/bin/sh\n")
        p.chmod(0o755)
    monkeypatch.delenv("DOCANON_SOFFICE", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(convert, "_MAC_SOFFICE", tmp_path / "no.app")
    monkeypatch.setattr(convert, "_WIN_PROGRAM_DIRS", ())
    monkeypatch.setattr(convert, "_IS_WINDOWS", True)
    monkeypatch.setattr("docanon_core.resources.path", lambda key: tmp_path / "libreoffice")
    return program


def test_bundled_soffice_matches_windows_file_names(tmp_path, monkeypatch):
    """Windows 上二进制叫 soffice.com / soffice.exe —— 直接 rglob(“soffice”) 一个都匹配不到。"""
    program = _bundled_tree(tmp_path, monkeypatch, "soffice.exe")

    assert convert.find_soffice() == program / "soffice.exe"


def test_bundled_soffice_prefers_the_console_binary(tmp_path, monkeypatch):
    """两个都在时选 soffice.com: 无控制台的那个会丢 stdout/stderr、甚至提前返回。"""
    program = _bundled_tree(tmp_path, monkeypatch, "soffice.exe", "soffice.com")

    assert convert.find_soffice() == program / "soffice.com"


def test_windows_path_hit_is_upgraded_to_the_console_binary(tmp_path, monkeypatch):
    """which() 命中的是 .exe; 同目录有 .com 就该换过去 —— to_modern 靠输出判失败, 拿 .exe 会误判。"""
    program = tmp_path / "program"
    program.mkdir()
    for name in ("soffice.com", "soffice.exe"):
        p = program / name
        p.write_bytes(b"#!/bin/sh\n")
        p.chmod(0o755)
    monkeypatch.setattr(convert, "_IS_WINDOWS", True)
    monkeypatch.setattr("shutil.which", lambda name: str(program / "soffice.exe"))

    assert convert.find_soffice() == program / "soffice.com"


def test_windows_install_outside_path_is_found(tmp_path, monkeypatch):
    """Windows 的安装器不改 PATH —— which() 命不中时还要查固定安装位。"""
    program = tmp_path / "LibreOffice" / "program"
    program.mkdir(parents=True)
    (program / "soffice.com").write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr(convert, "_IS_WINDOWS", True)
    monkeypatch.setattr(convert, "_WIN_PROGRAM_DIRS", (program,))
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert convert.find_soffice() == program / "soffice.com"


def test_exec_bit_is_not_checked_on_windows(tmp_path, monkeypatch):
    """Windows 没有执行位: 那边不能把「没置执行位」当成不可用, 否则下下来的那份永远读不到。"""
    plain = tmp_path / "soffice.exe"
    plain.write_bytes(b"#!/bin/sh\n")
    plain.chmod(0o644)

    assert convert._usable(plain) is False, "mac/Linux 上没执行位就是不可用"
    monkeypatch.setattr(convert, "_IS_WINDOWS", True)
    assert convert._usable(plain) is True, "Windows 上看不出执行位, 只能退到「文件存在」"
