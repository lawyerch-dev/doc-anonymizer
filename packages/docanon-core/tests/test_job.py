"""断点续跑的账本行为: 每文件落盘、中断可接、产物不在就重做、坏账本拒绝执行。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import docanon_core.job as job_module
from docanon_core.cli import main


@pytest.fixture
def calls(monkeypatch):
    """记录 process_file 实际被调了几次、都是谁。"""
    real = job_module.process_file
    seen: list[str] = []

    def spy(path, out_dir, config, store, rel=None):
        seen.append(str(rel or path))
        return real(path, out_dir, config, store, rel=rel)

    monkeypatch.setattr(job_module, "process_file", spy)
    return seen


def _case(tmp_path) -> Path:
    src = tmp_path / "案件"
    src.mkdir()
    (src / "甲.txt").write_text("张三 13812340000\n", encoding="utf-8")
    (src / "乙.txt").write_text("李四 13900001111\n", encoding="utf-8")
    return src


def _manifest(out: Path) -> dict:
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))


def test_ledger_lands_per_file_and_survives_interrupt(tmp_path, monkeypatch):
    """Ctrl+C 在第 2 个文件: 第 1 个必须已经在账本里, 且它的原文还能还原。"""
    src = _case(tmp_path)
    real = job_module.process_file
    out = tmp_path / "out"
    seen: list[str] = []
    phones = {"甲.txt": "13812340000", "乙.txt": "13900001111"}

    def spy(path, out_dir, config, store, rel=None):
        seen.append(str(rel or path))
        if len(seen) == 2:  # 不论谁排在前面, 都在第二个文件上中断
            raise KeyboardInterrupt
        return real(path, out_dir, config, store, rel=rel)

    monkeypatch.setattr(job_module, "process_file", spy)

    code = main(["run", str(src), "-o", str(out)])

    assert code == 2, "被中断不能报成功"
    assert len(seen) == 2
    manifest = _manifest(out)
    assert manifest["summary"]["processed"] == 1
    first = manifest["files"][0]["source"]
    originals = json.loads((out / "mapping.json").read_text(encoding="utf-8"))["reverse"].values()
    assert phones[first] in originals, "中断不能把已做文件的原文丢掉"


def test_resume_skips_finished_files(tmp_path, calls):
    src = _case(tmp_path)
    out = tmp_path / "out"
    assert main(["run", str(src), "-o", str(out)]) == 0
    assert len(calls) == 2
    calls.clear()

    assert main(["run", str(src), "-o", str(out), "--resume"]) == 0
    assert calls == [], "续跑不该把已脱敏的文件再跑一遍"
    assert _manifest(out)["summary"]["processed"] == 2


def test_resume_redoes_file_whose_output_is_gone(tmp_path, calls):
    """账本说做过、文件却不在 = 漏脱敏的入口, 必须重做。"""
    src = _case(tmp_path)
    out = tmp_path / "out"
    assert main(["run", str(src), "-o", str(out)]) == 0
    (out / "【脱敏版】甲.txt").unlink()
    calls.clear()

    assert main(["run", str(src), "-o", str(out), "--resume"]) == 0
    assert calls == ["甲.txt"]
    assert (out / "【脱敏版】甲.txt").exists()


def test_resume_retries_error_entries(tmp_path, calls):
    src = tmp_path / "案件"
    src.mkdir()
    (src / "坏.pdf").write_bytes(b"this is not a pdf")
    (src / "好.txt").write_text("张三 13812340000\n", encoding="utf-8")
    out = tmp_path / "out"

    assert main(["run", str(src), "-o", str(out)]) == 2
    calls.clear()

    assert main(["run", str(src), "-o", str(out), "--resume"]) == 2
    assert "坏.pdf" in calls, "上次失败的文件不能因为续跑就被跳过"


def test_corrupt_ledger_refuses_to_run(tmp_path, calls):
    src = _case(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "manifest.json").write_text("{ 半截的 JSON", encoding="utf-8")

    code = main(["run", str(src), "-o", str(out)])

    assert code == 1
    assert calls == [], "账本读不出来时一个文件都不该碰"
    assert (out / "manifest.json").read_text(encoding="utf-8").startswith("{ 半截")


def test_no_half_written_ledger_left_behind(tmp_path):
    src = _case(tmp_path)
    out = tmp_path / "out"
    assert main(["run", str(src), "-o", str(out)]) == 0
    assert not list(out.glob("*.tmp")), "原子写没做干净会留下 .tmp"
