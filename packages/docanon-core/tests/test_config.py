"""config_from_dict: 不落盘也能从字典构造 Config(Web 内联配置用)。"""
from __future__ import annotations

from docanon_core.config import config_from_dict


def test_config_from_dict_builds_from_plain_data():
    cfg = config_from_dict({
        "strategies": {"PERSON": "redact"},
        "dictionary": ["内部项目代号"],
        "detectors": {"rule": True},
        "onnx": {"model_dirs": ["var/models/onnx/gyr66"]},
        "llm": {"base_url": "http://127.0.0.1:9999/v1", "model": "custom"},
        "legacy_convert": False,
    })
    assert cfg.strategy_for("PERSON") == "redact"
    assert cfg.dictionary == ["内部项目代号"]
    assert cfg.detectors == {"rule": True}
    assert cfg.onnx.model_dirs == ["var/models/onnx/gyr66"]
    assert cfg.llm.base_url == "http://127.0.0.1:9999/v1"
    assert cfg.llm.model == "custom"
    assert cfg.legacy_convert is False


def test_config_from_dict_defaults_legacy_convert_true():
    cfg = config_from_dict({"detectors": {"rule": True}})
    assert cfg.legacy_convert is True
