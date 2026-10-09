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


def test_default_onnx_map_does_not_turn_roles_into_entities():
    """`position`(审判员/课题组组长/法定代表人…)默认不映射: 角色不是身份。

    实测一份真合同: 映射着的时候, ONNX 把"课题负责人：王茹月"打成"**：**"、"授权代表（签章）"
    左边抹右边留 —— 半截话比不抹更像"没脱干净"。要角色消失的人, 自己写 onnx.entity_map 加回去。
    """
    from docanon_core.config import DEFAULT_ONNX_ENTITY_MAP

    assert "position" not in DEFAULT_ONNX_ENTITY_MAP
    assert "POSITION" not in DEFAULT_ONNX_ENTITY_MAP.values()
