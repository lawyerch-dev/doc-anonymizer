"""首次"初始化"（按方案补模型）。

网络一律不打真: 测速与下载都 monkeypatch 掉。这里锁的是**逻辑**:
测速选快源、缺文件不算就绪、进度/取消、以及"一个文件都没有时也能判出未装"。
"""
from __future__ import annotations

import pathlib
import threading

import pytest

from docanon_core.config import config_from_dict
from docanon_core.server import prepare


def _reset_job() -> None:
    prepare._JOB.state = "idle"
    prepare._JOB.done_bytes = 0
    prepare._JOB.total_bytes = None
    prepare._JOB.error = None
    prepare._JOB.cancel.clear()


@pytest.fixture(autouse=True)
def _clean_job():
    _reset_job()
    yield
    _reset_job()


def _cfg(onnx_dirs: list[str], llm: bool = False) -> object:
    return config_from_dict({
        "detectors": {"rule": True, "dictionary": True, "onnx_ner": bool(onnx_dirs), "llm_ner": llm},
        "onnx": {"model_dirs": onnx_dirs},
        "llm": {"model_id": ""},
    })


def _install_fake_dir(tmp_path: pathlib.Path, model_id: str, files: list[str], *, full: bool) -> pathlib.Path:
    d = tmp_path / model_id
    d.mkdir(parents=True, exist_ok=True)
    for f in (files if full else files[:1]):
        (d / f).write_bytes(b"x")
    return d


# ---------- 目录与"装好没有" ----------

def test_catalog_reads_the_shipped_yaml():
    items = {i["id"]: i for i in prepare.catalog()}
    assert {"gyr66", "pii-engineer"} <= set(items)
    assert items["gyr66"]["repo"]          # 地址由 repo 拼, 不能空
    assert items["gyr66"]["files"]


def test_partial_files_do_not_count_as_installed(tmp_path, monkeypatch):
    """少一个文件就当没装 —— 否则运行时会"少一层", 而这里的职责正是别让它蒙混过去。"""
    item = {"id": "gyr66", "repo": "r", "files": ["a.onnx", "b.json"], "size_mb": 1}
    monkeypatch.setattr(prepare, "dir_for", lambda _id: tmp_path / "gyr66")
    _install_fake_dir(tmp_path, "gyr66", item["files"], full=False)

    assert prepare.installed(item) is False

    (tmp_path / "gyr66" / "b.json").write_bytes(b"x")
    assert prepare.installed(item) is True


def test_missing_ids_only_reports_configured_and_uninstalled(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "dir_for", lambda mid: tmp_path / mid)
    _install_fake_dir(tmp_path, "gyr66", ["config.json", "model.onnx"], full=True)  # 真文件清单不匹配 → 仍算未装
    cfg = _cfg(["var/models/onnx/gyr66", "var/models/onnx/自备模型"])

    # gyr66 的必需文件没齐 → 要下载; 自备模型不在目录里 → 不猜、不参与下载
    assert prepare.missing_ids(cfg) == ["gyr66"]


def test_needed_is_ready_when_onnx_off():
    cfg = _cfg([])
    plan = prepare.needed(cfg)
    assert plan["ready"] is True
    assert plan["onnx"] == []


# ---------- 未就绪时能不能把 Web 起起来 ----------

def test_startup_tolerates_missing_models_only_when_it_can_fix_them(tmp_path, monkeypatch):
    """打包后的首次使用: 装完还没模型, 而模型要在界面上点"准备"下 —— 这时不能退出。

    否则用户连那个按钮都看不到(实测: .app 启动即 `Web 未启动: 找不到 ONNX 模型` 然后退出)。
    但这条口子只对"有东西可准备"开: 没有可准备的东西时照旧退出, 免得把真故障也放成"未就绪"。
    """
    from docanon_core.server import _preparable

    monkeypatch.setattr(prepare, "dir_for", lambda mid: tmp_path / "onnx" / mid)

    assert _preparable(_cfg(["var/models/onnx/gyr66"])) is True      # 目录在, 但文件没下 → 可准备
    assert _preparable(_cfg([])) is False                            # 不用模型, 那就没有可准备的
    assert _preparable(_cfg(["var/models/onnx/自备模型"])) is False    # 目录里没登记 → 不该替用户去猜


# ---------- 测速选源 ----------

def test_requests_carry_a_user_agent():
    """hf-mirror 对没有 UA 的请求回 403(实测 config.json 403 / model.onnx 206)。

    少了这个头, 小文件会"全都下不动" —— 看起来像网络坏了, 其实是把请求挡在了门外。
    """
    assert prepare._headers().get("User-Agent")
    assert prepare._headers({"Range": "bytes=0-0"})["User-Agent"]


def test_speed_probe_uses_the_weight_file_not_the_longest_name():
    """测速要拿权重测真带宽; 按"文件名最长"去挑会挑中 special_tokens_map.json。"""
    item = {"files": ["config.json", "special_tokens_map.json", "model.onnx", "vocab.txt"]}
    assert prepare._weight_of(item) == "model.onnx"
    assert prepare._weight_of({"files": ["model.onnx.data", "model.onnx"]}) == "model.onnx.data"
    assert prepare._weight_of({"files": ["only.json"]}) == "only.json"


def test_size_from_prefers_content_range():
    """带 Range 时总大小在 `Content-Range` 尾部; 不支持 Range 的服务才看 `Content-Length`。"""
    assert prepare._size_from({"Content-Range": "bytes 0-0/407063645", "Content-Length": "1"}) == 407063645
    assert prepare._size_from({"Content-Length": "1234"}) == 1234
    assert prepare._size_from({}) is None


def test_pick_endpoint_chooses_the_faster_one(monkeypatch):
    speeds = {"https://hf-mirror.com": 1.0, "https://huggingface.co": 5.0}
    monkeypatch.setattr(prepare, "_endpoint_speed", lambda base, _item: speeds.get(base, 0.0))

    assert prepare.pick_endpoint({"id": "x", "repo": "r", "files": ["model.onnx"]}) == "https://huggingface.co"


def test_pick_endpoint_raises_when_nothing_reachable(monkeypatch):
    """全部不通要报错, 不能静默退回一个"猜"的地址。"""
    monkeypatch.setattr(prepare, "_endpoint_speed", lambda _base, _item: 0.0)

    with pytest.raises(prepare.PrepareError) as exc:
        prepare.pick_endpoint({"id": "x", "repo": "r", "files": ["model.onnx"]})
    assert "网络" in str(exc.value)


# ---------- 任务: 下载 / 进度 / 取消 ----------

def test_start_downloads_missing_files_and_reports_done(tmp_path, monkeypatch):
    """两个文件: 假下载器把它们写齐, 任务报 done; 中途进度可见。"""
    item = {"id": "gyr66", "repo": "r", "files": ["a.bin", "b.bin"], "size_mb": 1}
    monkeypatch.setattr(prepare, "catalog", lambda: [item])
    monkeypatch.setattr(prepare, "dir_for", lambda _id: tmp_path / "gyr66")
    monkeypatch.setattr(prepare, "pick_endpoint", lambda _item: "https://mirror")
    monkeypatch.setattr(prepare, "_probe_total", lambda *_a: 100)

    seen: list[int] = []

    def fake_fetch(_base, _repo, name, dest: pathlib.Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"y" * 50)
        with prepare._JOB.lock:
            prepare._JOB.done_bytes += 50
        seen.append(prepare.status()["done_bytes"])

    monkeypatch.setattr(prepare, "_fetch", fake_fetch)
    cfg = _cfg(["var/models/onnx/gyr66"])

    first = prepare.start(cfg)
    assert first["state"] == "running"

    for _ in range(50):
        if prepare.status()["state"] != "running":
            break
        threading.Event().wait(0.02)

    st = prepare.status()
    assert st["state"] == "done"
    assert st["total_bytes"] == 100
    assert seen, "进度回调没被观察到"


def test_start_is_a_noop_when_everything_is_installed(monkeypatch):
    monkeypatch.setattr(prepare, "catalog", lambda: [
        {"id": "gyr66", "repo": "r", "files": ["a"], "size_mb": 1}
    ])
    monkeypatch.setattr(prepare, "installed", lambda _item: True)
    cfg = _cfg(["var/models/onnx/gyr66"])

    assert prepare.start(cfg)["state"] == "done"


def test_cancel_stops_the_job_and_keeps_what_was_downloaded(tmp_path, monkeypatch):
    item = {"id": "gyr66", "repo": "r", "files": ["a.bin", "b.bin"], "size_mb": 1}
    monkeypatch.setattr(prepare, "catalog", lambda: [item])
    monkeypatch.setattr(prepare, "dir_for", lambda _id: tmp_path / "gyr66")
    monkeypatch.setattr(prepare, "pick_endpoint", lambda _item: "https://mirror")
    monkeypatch.setattr(prepare, "_probe_total", lambda *_a: 100)

    started = threading.Event()

    def linger(_base, _repo, name, dest: pathlib.Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"y" * 10)
        started.set()
        prepare._JOB.cancel.wait(2)      # 停在这里, 等测试按取消

    monkeypatch.setattr(prepare, "_fetch", linger)
    prepare.start(_cfg(["var/models/onnx/gyr66"]))
    assert started.wait(3), "第一个文件还没开始下, 取消就无从谈起"
    prepare.cancel()

    for _ in range(80):
        if prepare.status()["state"] != "running":
            break
        threading.Event().wait(0.02)

    assert prepare.status()["state"] == "cancelled"
    assert (tmp_path / "gyr66" / "a.bin").is_file(), "已下好的文件要留着(下次接着补)"
