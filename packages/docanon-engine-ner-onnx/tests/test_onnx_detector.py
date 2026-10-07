"""ONNX NER 引擎自己的测试: 不经过 core。

这个引擎的契约是"构造即加载": 模型/词表有问题就在构造时报错 —— 一个起不来的引擎必须留下
痕迹, 不能静默返回零命中。真模型在 `var/models/onnx/`(gitignore), 没有就 skip 掉依赖它的几条。
"""
from __future__ import annotations

import pathlib

import pytest

from docanon_contract import Block
from docanon_engine_ner_onnx import OnnxNERDetector

REPO = pathlib.Path(__file__).resolve().parents[3]
MODEL_DIR = REPO / "var" / "models" / "onnx" / "gyr66"

# 引擎不认识 PERSON/ORG 这些名字: 词表是 app 侧传进来的必填参数
ENTITY_MAP = {"name": "PERSON", "organization": "ORG", "company": "ORG", "address": "LOCATION"}
TEXT = "汇报人：张三，华信集团有限公司负责本季度经营分析。"

needs_model = pytest.mark.skipif(
    not MODEL_DIR.is_dir(), reason="var/models/onnx/gyr66 不在(未下载模型)"
)


def test_entity_map_is_required_not_defaulted(tmp_path):
    """引擎自带词表 = 词表跟着引擎仓库走, 移植时必然漂移; 所以它是必填参数。"""
    with pytest.raises(ValueError, match="映射表"):
        OnnxNERDetector(tmp_path, {})


def test_missing_model_fails_loudly_at_construction(tmp_path):
    """模型不在 → 构造就报错(而不是等到 detect 时静默返回空)。"""
    with pytest.raises(FileNotFoundError, match="model.onnx"):
        OnnxNERDetector(tmp_path, dict(ENTITY_MAP))


@needs_model
def test_ready_and_capabilities_with_the_real_model():
    det = OnnxNERDetector(MODEL_DIR, dict(ENTITY_MAP))
    assert det.ready() is None, f"模型在却起不来: {det.ready()}"
    assert set(det.capabilities()) == set(ENTITY_MAP.values())


@needs_model
def test_detects_entities_and_spans_point_back_into_the_text():
    found = OnnxNERDetector(MODEL_DIR, dict(ENTITY_MAP)).detect(Block("p0", TEXT))

    types = {d.entity_type for d in found}
    assert found, "真模型上一个实体都没识别出来"
    assert types & {"PERSON", "ORG"}, f"没认出人名/机构, 实际是 {types}"
    for d in found:
        assert 0 <= d.span.start < d.span.end <= len(TEXT)
        assert TEXT[d.span.start : d.span.end], "span 必须落在原文里"


@needs_model
def test_labels_outside_the_map_are_ignored():
    """app 没映射的标签必须被忽略 —— 否则会冒出 app 不认识的实体类型。"""
    found = OnnxNERDetector(MODEL_DIR, {"name": "PERSON"}).detect(Block("p0", TEXT))
    assert {d.entity_type for d in found} <= {"PERSON"}
