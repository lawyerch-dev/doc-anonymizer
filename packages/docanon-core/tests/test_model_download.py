"""模型目录 + 界面内下载: 目录结构、URL 拼接、以及"拒绝面"。

**不真下载**: 2.7GB 不可能在测试里跑。这里只覆盖状态机、参数校验、URL 拼接 ——
以及一条安全约束: **下载地址只能由仓库内的目录拼出**, 接口不接受任意 URL。
"""
from __future__ import annotations

import pathlib
import re

import pytest

from docanon_core.server import downloads


def test_catalog_entries_are_complete_and_unique():
    items = downloads.catalog()
    assert items, "目录是空的?"
    ids = [it["id"] for it in items]
    assert len(set(ids)) == len(ids), f"id 重复: {ids}"
    for it in items:
        assert it["name"] and it["hint"], f"{it['id']} 缺给用户看的名字/说明"
        assert it["repo"], f"{it['id']} 缺 repo"
        assert isinstance(it["size_gb"], float) and it["size_gb"] > 0, it["id"]


def test_catalog_file_is_a_bare_filename():
    """`file` 会被拼进 URL、也会被当成本地落盘名 —— 带路径就是穿越。"""
    for it in downloads.catalog():
        assert it["file"] == pathlib.PurePosixPath(it["file"]).name, it["file"]
        assert "/" not in it["file"] and "\\" not in it["file"], it["file"]
        assert not it["file"].startswith("."), it["file"]


def test_url_is_built_only_from_the_catalog():
    """地址必须是"仓库目录 + 文件名"拼出来的确定值(不接受任何请求侧输入)。"""
    item = downloads.entry("qwen3.8-4b-distill")
    assert downloads.url_for(item) == (
        "https://www.modelscope.cn/models/empero-ai/Qwen3.8-4B-Distill-GGUF"
        "/resolve/master/Qwen3.8-4B-Q4_K_M.gguf"
    )


def test_model_path_stays_inside_models_dir():
    """落盘位置必须就在 var/models/ 下, 不许因为目录里写了怪名字而跑到别处。"""
    for it in downloads.catalog():
        p = downloads.model_path(it)
        assert p.parent == downloads.resources.path("models")
        assert p.name == it["file"]


def test_broken_catalog_is_a_loud_error(tmp_path, monkeypatch):
    """目录缺字段 / file 带路径 → 报错, 不许退化成一个空列表。"""
    broken = tmp_path / downloads.CATALOG
    monkeypatch.setattr(downloads.resources, "config_path", lambda _name: broken)

    broken.write_text("models: []\n", encoding="utf-8")
    with pytest.raises(downloads.DownloadError, match="没有 models 列表"):
        downloads.catalog()

    broken.write_text("models:\n  - id: a\n    name: n\n    hint: h\n", encoding="utf-8")
    with pytest.raises(downloads.DownloadError, match="缺字段"):
        downloads.catalog()

    broken.write_text(
        "models:\n  - id: a\n    name: n\n    hint: h\n    repo: r\n"
        "    file: ../evil.gguf\n    size_gb: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(downloads.DownloadError, match="纯文件名"):
        downloads.catalog()


def test_unknown_id_is_rejected():
    with pytest.raises(downloads.DownloadError, match="没有这个 id"):
        downloads.entry("nope")


def test_list_models_marks_what_is_already_downloaded(monkeypatch):
    monkeypatch.setattr(downloads, "is_downloaded", lambda it: it["id"] == "qwen3.5-4b")
    rows = {it["id"]: it["downloaded"] for it in downloads.list_models()}
    assert rows == {"qwen3.8-4b-distill": False, "qwen3.5-4b": True}


def test_idle_state_shape_before_anything_runs():
    """没跑过任务时是 idle —— 界面据此显示"未开始", 不是"失败"。"""
    state = downloads.status()
    assert state["state"] in ("idle", "done", "error", "cancelled", "downloading")
    assert set(state) == {"id", "state", "done_bytes", "total_bytes", "error"}


def test_second_start_while_busy_is_a_conflict(monkeypatch):
    """已有任务在跑时再点一次 → 409(带原因), 不排队也不静默忽略。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: False)
    monkeypatch.setattr(downloads._JOB, "state", "downloading", raising=False)
    monkeypatch.setattr(downloads._JOB, "id", "qwen3.8-4b-distill", raising=False)
    # 万一真起了线程, 让它别碰网络
    monkeypatch.setattr(downloads, "_run", lambda _it: None)
    try:
        with pytest.raises(downloads.DownloadError) as excinfo:
            downloads.start("qwen3.5-4b")
        assert excinfo.value.code == 409
        assert "已经有一个下载任务" in str(excinfo.value)
    finally:
        downloads._JOB.state = "idle"
        downloads._JOB.id = None


def test_download_script_agrees_with_the_catalog(repo_root):
    """`scripts/download_model.sh` 是终端里的老路, 目录是界面里的新路 —— 同一份事实不许说两样。

    脚本只支持"默认那个模型"的各量化档(带 ${QUANT} 占位), 这里锁住它下的就是目录里推荐的那条;
    以后改了一边忘了另一边, 这条会红。
    """
    script = (repo_root / "scripts" / "download_model.sh").read_text(encoding="utf-8")
    repo = re.search(r'^REPO="([^"]+)"', script, re.M)
    file_tpl = re.search(r'^FILE="([^"]+)"', script, re.M)
    assert repo and file_tpl, "download_model.sh 里的 REPO / FILE 读不出来(改名了?)"
    item = downloads.entry("qwen3.8-4b-distill")
    assert repo.group(1) == item["repo"], "脚本的仓库与模型目录不一致"
    assert file_tpl.group(1).replace("${QUANT}", "Q4_K_M") == item["file"], "脚本的文件名与目录不一致"


def test_start_refuses_when_already_downloaded(monkeypatch):
    """已经下过了就别再下 2.7G —— 给一句能照做的话(要重下先删掉)。"""
    monkeypatch.setattr(downloads, "is_downloaded", lambda _it: True)
    with pytest.raises(downloads.DownloadError) as excinfo:
        downloads.start("qwen3.5-4b")
    assert excinfo.value.code == 409
    assert "已经下载过" in str(excinfo.value)
