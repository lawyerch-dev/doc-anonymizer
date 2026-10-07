"""LLM 子包(本地大模型引擎的传输层)。"""
from .client import LLMClient, LLMConfig, LLMError

__all__ = ["LLMClient", "LLMConfig", "LLMError"]
