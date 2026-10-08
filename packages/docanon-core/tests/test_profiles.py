"""Web 用户配置: 名字规则 / 归一化 / 结构校验。"""
from __future__ import annotations

import pytest

from docanon_core.detectors import DETECTORS
from docanon_core.server import profiles


def test_detector_names_do_not_drift_from_registry():
    assert set(profiles.DETECTOR_NAMES) == set(DETECTORS)


@pytest.mark.parametrize("name", ["mine", "my-cfg_1", "A" * 32])
def test_validate_name_accepts_safe_names(name):
    profiles.validate_name(name)  # 不抛即通过


@pytest.mark.parametrize("name", ["../x", "a/b", "a.b", "", "x" * 33, "默认"])
def test_validate_name_rejects_dangerous_names(name):
    with pytest.raises(profiles.ProfileError):
        profiles.validate_name(name)


def test_is_builtin_distinguishes_by_extension():
    assert profiles.is_builtin("onnx.yaml")
    assert not profiles.is_builtin("mine")


def test_normalize_fills_missing_keys_from_default():
    out = profiles.normalize({"strategies": {"PERSON": "redact"}})
    assert out["strategies"] == {"PERSON": "redact"}
    assert set(profiles.EDITABLE_KEYS) <= set(out)
    assert out["detectors"].get("rule") is True  # 来自 default.yaml


def test_validate_rejects_unknown_strategy():
    with pytest.raises(profiles.ProfileError, match="未知策略值"):
        profiles.validate({"strategies": {"PERSON": "shred"}})


def test_validate_rejects_all_detectors_off():
    with pytest.raises(profiles.ProfileError, match="检测器"):
        profiles.validate({"detectors": {"rule": False, "dictionary": False,
                                         "onnx_ner": False, "llm_ner": False}})


def test_validate_rejects_unknown_detector_name():
    with pytest.raises(profiles.ProfileError, match="未知检测器"):
        profiles.validate({"detectors": {"rule": True, "magic": True}})


def test_validate_rejects_bad_model_dirs_type():
    with pytest.raises(profiles.ProfileError, match="model_dirs"):
        profiles.validate({"onnx": {"model_dirs": "not-a-list"}})


def test_validate_accepts_partial_onnx_entity_map_only():
    profiles.validate({"onnx": {"entity_map": {"name": "PERSON"}}})  # 不抛即通过
    assert isinstance(profiles.normalize({"onnx": {"entity_map": {"name": "PERSON"}}})["onnx"]["model_dirs"], list)


def test_normalize_fills_missing_onnx_model_dirs():
    assert isinstance(profiles.normalize({"onnx": {}})["onnx"]["model_dirs"], list)

