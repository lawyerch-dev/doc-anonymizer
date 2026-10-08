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


import yaml


def _isolate(tmp_path, monkeypatch):
    """把用户配置目录指到 tmp_path, 免得污染真实 var/。"""
    monkeypatch.setattr(profiles, "user_dir", lambda: tmp_path / "var" / "configs")


def test_save_load_delete_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    data = profiles.normalize({"strategies": {"PERSON": "pseudonym"}})

    profiles.save_profile("mine", data)
    assert (tmp_path / "var" / "configs" / "mine.yaml").is_file()

    loaded = profiles.load_profile("mine")
    assert loaded["strategies"]["PERSON"] == "pseudonym"
    assert set(profiles.EDITABLE_KEYS) <= set(loaded)

    profiles.delete_profile("mine")
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile("mine")


def test_save_rejects_dangerous_name(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with pytest.raises(profiles.ProfileError):
        profiles.save_profile("../evil", {"detectors": {"rule": True}})


def test_list_profiles_marks_builtin_and_user(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    profiles.save_profile("mine", profiles.normalize({}))

    rows = {r["name"]: r for r in profiles.list_profiles(current="mine")}
    assert rows["onnx.yaml"]["kind"] == "builtin"
    assert rows["mine"]["kind"] == "user"
    assert rows["mine"]["current"] is True
    assert rows["mine"]["label"]


def test_load_half_yaml_is_normalized(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # 直接手写半截文件, 模拟"用户只写了 strategies 的 yaml"
    d = tmp_path / "var" / "configs"
    d.mkdir(parents=True)
    (d / "half.yaml").write_text("strategies:\n  PERSON: redact\n", encoding="utf-8")

    loaded = profiles.load_profile("half")
    assert loaded["strategies"] == {"PERSON": "redact"}
    assert loaded["detectors"].get("rule") is True


def test_import_and_export_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    text = "strategies:\n  ORG: redact\ndetectors:\n  rule: true\n"
    name = profiles.import_yaml("from-file.yaml", text)
    assert name == "from-file"

    out = profiles.export_yaml("from-file")
    assert "ORG: redact" in out and "rule: true" in out


def test_builtin_cannot_be_deleted(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with pytest.raises(profiles.ProfileError):
        # 同名内置不落用户目录: 删除内置名会因"用户配置不存在"而拒绝
        profiles.delete_profile("default.yaml")


def test_available_onnx_dirs_lists_relative_dirs():
    rows = profiles.available_onnx_dirs()
    assert isinstance(rows, list)
    assert all(d.startswith("var/models/onnx/") for d in rows)


def test_bad_encoding_file_does_not_break_listing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    d = tmp_path / "var" / "configs"
    d.mkdir(parents=True)
    (d / "bad.yaml").write_bytes(b"\xff\xfe\x00not utf8")

    rows = {r["name"]: r for r in profiles.list_profiles(current="default.yaml")}
    assert rows["bad"]["kind"] == "user"
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile("bad")

