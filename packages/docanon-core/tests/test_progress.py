"""跑一份文档时的进度与取消: 状态可读、取消不留半成品。

背景: 最准档跑一份 5000 字的合同要 30-40 秒, 界面上只有一句"脱敏中…" —— 看不见、也没法中止。
"""
from __future__ import annotations

import threading

import pytest

from docanon_core.config import load_config
from docanon_core.pipeline import Cancelled, process_file
from docanon_core.redaction.mapping import MappingStore
from docanon_core.server import progress


@pytest.fixture(autouse=True)
def _clean():
    progress.clear()
    yield
    progress.clear()


def test_job_id_must_be_safe():
    """job id 会被当字典键 —— 只收字母数字下划线与连字符。"""
    for bad in ("", "../x", "a/b", "a" * 33, "默认"):
        with pytest.raises(progress.BadJobId):
            progress.begin(bad)


def test_state_roundtrip_and_finish():
    assert progress.state("nope")["stage"] == "unknown"
    cancel = progress.begin("job-1")
    assert cancel.is_set() is False
    progress.update("job-1", "detect", 3, 101)
    got = progress.state("job-1")
    assert (got["stage"], got["done"], got["total"]) == ("detect", 3, 101)
    assert progress.cancel("job-1") is True
    assert cancel.is_set() and progress.state("job-1")["cancelled"] is True
    progress.finish("job-1")
    assert progress.state("job-1")["stage"] == "done"


def test_cancel_unknown_job_is_false():
    assert progress.cancel("nope") is False


def test_table_is_capped():
    """长期开着的服务不该把历史任务全记着: 攒够了先丢最早的一半。"""
    for i in range(progress.MAX_JOBS + 5):
        progress.begin(f"job-{i}")
    assert progress.state("job-0")["stage"] == "unknown"
    assert progress.state(f"job-{progress.MAX_JOBS + 4}")["stage"] == "extract"


def test_progress_callback_sees_each_stage(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("张三 13812340000\n", encoding="utf-8")

    seen: list[tuple] = []
    process_file(src, tmp_path / "out", load_config(), MappingStore(),
                 progress=lambda stage, done, total: seen.append((stage, done, total)))

    assert [s for s, _, _ in seen][:2] == ["extract", "detect"]
    assert seen[1][1:] == (1, 1)      # 单块文件: 第 1/1 段
    assert seen[-1][0] == "write"


def test_cancel_before_writing_leaves_no_output(tmp_path):
    """取消 = 一个产物都不留(半截产物比没产物更危险)。"""
    src = tmp_path / "a.txt"
    src.write_text("张三 13812340000\n", encoding="utf-8")

    cancel = threading.Event()
    cancel.set()                      # 一开跑就取消
    with pytest.raises(Cancelled):
        process_file(src, tmp_path / "out", load_config(), MappingStore(), cancel=cancel)

    out = tmp_path / "out"
    assert not out.exists() or not list(out.rglob("【脱敏版】*"))
