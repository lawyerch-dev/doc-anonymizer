"""docanon-engine-ner-llm: 本地大模型 NER 引擎(llama-server, OpenAI 兼容)。

`client.py` 是传输层(LLMClient/LLMConfig/LLMError), `detector.py` 是检测器。
只依赖标准库 + docanon-contract, 不 import app(core) 与另一个引擎。
"""
from .client import LLMClient, LLMConfig, LLMError
from .detector import LLMNERDetector

__all__ = ["LLMClient", "LLMConfig", "LLMError", "LLMNERDetector"]
