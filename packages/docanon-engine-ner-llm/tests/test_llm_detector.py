"""LLM NER 引擎自己的测试: 不经过 core, 也不需要真的起 llama-server。

关键性质: 端点答不上来必须**抛错**, 不许静默返回空 —— 一次"没答上来"被当成"零命中",
就等于一份没脱敏的文档被报成已脱敏。回归测试: tests/test_restore.py 那条事故的同族。
"""
from __future__ import annotations

import pytest

from docanon_contract import Block
from docanon_engine_ner_llm import LLMClient, LLMConfig, LLMError, LLMNERDetector

# 9 号端口是 discard 服务, 基本不会有东西应答 —— 用"连不上"来测失败路径
DEAD = LLMConfig(base_url="http://127.0.0.1:9/v1", timeout=2)


def test_config_belongs_to_the_engine_and_has_sane_defaults():
    cfg = LLMConfig()
    assert cfg.base_url.endswith("/v1")
    assert cfg.model and cfg.timeout > 0 and cfg.chunk_size > 0
    assert cfg.disable_thinking is True, "默认关掉 Qwen3.x 的思考模式, 直接出 JSON"


def test_ready_explains_why_it_cannot_work():
    det = LLMNERDetector(DEAD)
    reason = det.ready()
    assert reason and "llama-server" in reason, f"起不来要给原因, 实际: {reason!r}"


def test_capabilities_are_the_fixed_label_set():
    assert set(LLMNERDetector(DEAD).capabilities()) == {
        "PERSON",
        "ORG",
        "LOCATION",
        "AMOUNT",
        "SECRET",
        "CUSTOM",
    }


def test_endpoint_failure_raises_instead_of_returning_no_hits():
    det = LLMNERDetector(DEAD)
    with pytest.raises(LLMError):
        det.detect(Block("p0", "汇报人：张三"))


def test_client_raises_llm_error_and_keeps_the_cause():
    with pytest.raises(LLMError) as exc:
        LLMClient(DEAD).chat("system", "user")
    assert "调不通" in str(exc.value)


def test_detector_name_and_types_are_engine_side():
    """引擎只认自己那套标签; app 的注册表键名(llm_ner)不在引擎里。"""
    det = LLMNERDetector(DEAD)
    assert det.name == "llm"
    assert not hasattr(type(det), "DEFAULT_ENTITY_MAP")
