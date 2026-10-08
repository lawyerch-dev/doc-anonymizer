"""引擎层: 进程级缓存、注册表校验、健康预检、资源根解析。"""
from __future__ import annotations

import json

import pytest

from docanon_core import resources
from docanon_core.cli import main
from docanon_core.config import load_config
from docanon_contract import Block
from docanon_core.detectors import build_detectors, clear_detector_cache
from docanon_engine_ner_llm import LLMNERDetector
from docanon_engine_ner_llm import LLMClient, LLMConfig, LLMError

REPO = resources.root()
ONNX_DIRS = ("var/models/onnx/gyr66", "var/models/onnx/pii-engineer")
ONNX_READY = all((REPO / d / "model.onnx").exists() for d in ONNX_DIRS)


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    clear_detector_cache()
    yield
    clear_detector_cache()


def _cfg(**detectors) -> object:
    cfg = load_config()
    cfg.detectors = {**cfg.detectors, **detectors}
    return cfg


def test_same_config_reuses_one_engine_set():
    """逐文件重载 ONNX 会话是原来最贵的开销, 这里锁住"一个进程只加载一次"。"""
    cfg = load_config()
    assert build_detectors(cfg) is build_detectors(cfg)
    assert build_detectors(cfg) is build_detectors(load_config())
    # 指纹不同(多开了一个引擎)就必须重建, 不能拿旧缓存糊弄
    assert build_detectors(cfg) is not build_detectors(_cfg(llm_ner=True))


def test_unknown_detector_name_is_rejected():
    cfg = load_config()
    cfg.detectors = {"rule": True, "onnx_nerr": True}  # 拼错的引擎名
    with pytest.raises(ValueError, match="onnx_nerr"):
        build_detectors(cfg)


def test_all_detectors_off_is_rejected():
    cfg = load_config()
    cfg.detectors = {}
    with pytest.raises(ValueError, match="没有任何启用的检测器"):
        build_detectors(cfg)


def _llm(monkeypatch, reply=None, error=None) -> LLMNERDetector:
    d = LLMNERDetector(LLMConfig())
    if error is not None:
        def boom(*_args, **_kwargs):
            raise error
        monkeypatch.setattr(LLMClient, "chat", boom)
    else:
        monkeypatch.setattr(LLMClient, "chat", lambda self, *_a, **_k: reply)
    return d


def test_llm_transport_failure_is_not_a_silent_zero(monkeypatch):
    d = _llm(monkeypatch, error=LLMError("127.0.0.1:8080 调不通"))
    with pytest.raises(LLMError):
        d.detect(Block("b", "张三 13812340000"))


def test_llm_unparseable_reply_is_not_a_silent_zero(monkeypatch):
    d = _llm(monkeypatch, reply="抱歉, 这段文字里没有敏感信息。")
    with pytest.raises(LLMError, match="解析不出实体数组"):
        d.detect(Block("b", "张三 13812340000"))


def test_llm_empty_array_reply_is_fine(monkeypatch):
    d = _llm(monkeypatch, reply="[]")
    assert d.detect(Block("b", "普通的一段话")) == []


def test_run_refuses_to_write_when_an_engine_is_down(tmp_path, monkeypatch):
    """llm_ner 开着但 llama-server 没起: 必须零产物退出, 不能出一份少了实体层的"脱敏件"。"""
    cfg_file = tmp_path / "llm.yaml"
    cfg_file.write_text(
        "strategies: {DEFAULT: placeholder}\ndetectors: {rule: true, llm_ner: true}\n",
        encoding="utf-8",
    )
    doc = tmp_path / "甲.txt"
    doc.write_text("张三 13812340000\n", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(LLMClient, "health", lambda self: False)

    code = main(["run", str(doc), "-o", str(out), "-c", str(cfg_file)])

    assert code == 1
    assert not out.exists(), "预检失败时连输出目录都不该建"


@pytest.mark.skipif(not ONNX_READY, reason="未下载 ONNX 模型")
def test_relative_model_dirs_resolve_from_resource_root_not_cwd(tmp_path, monkeypatch):
    """configs 里的 var/models/onnx/... 是相对资源根的路径, 换目录跑不该变成零产物。"""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "o"

    code = main([
        "run", str(REPO / "samples" / "example.txt"),
        "-o", str(out), "-c", "configs/onnx.yaml",
    ])

    assert code == 0
    entry = json.loads((out / "manifest.json").read_text(encoding="utf-8"))["files"][0]
    assert entry["counts"].get("PERSON") == 1, "ONNX 没加载成功就等于静默少一层检测"
    assert "13812340000" not in (out / "example.txt.redacted.txt").read_text(encoding="utf-8")


def test_missing_config_is_an_error_not_a_fallback(tmp_path):
    doc = tmp_path / "甲.txt"
    doc.write_text("张三 13812340000\n", encoding="utf-8")
    missing = tmp_path / "nope.yaml"

    code = main(["run", str(doc), "-o", str(tmp_path / "out"), "-c", str(missing)])

    assert code == 1, "读不到指定配置却按内置默认跑, 就是少一层检测还报成功"
    assert not (tmp_path / "out").exists()


def test_engines_reports_legacy_office_status(monkeypatch):
    """旧格式抽取器要如实自述可用性(缺 soffice 就说原因), 而不是一律"已登记"。"""
    from docanon_core import inventory
    from docanon_core.config import Config

    monkeypatch.setattr("docanon_core.convert.find_soffice", lambda: None)
    rows = {r["name"]: r for r in inventory.list_engines(Config(detectors={}))}
    assert rows["legacy_office"]["status"].startswith("不可用")
    assert "LibreOffice" in rows["legacy_office"]["status"]


def test_engines_exit_ok_when_only_optional_converter_missing(tmp_path, monkeypatch):
    """可选转换器(旧格式)缺席不该把整份引擎清单判成失败 —— 报告 ≠ 门禁。"""
    monkeypatch.setattr("docanon_core.convert.find_soffice", lambda: None)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("detectors: {rule: true}\n", encoding="utf-8")

    code = main(["engines", "-c", str(cfg)])

    assert code == 0
