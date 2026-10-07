"""docanon-engine-ner-onnx: 本地 ONNX 中文 NER 引擎(编码器式, 无 server)。

实体词表由 app 侧传入(引擎不认识 PERSON/ORG 这些名字), 见 docanon_core.config。
只依赖 docanon-contract 与第三方推理库, 不 import app(core) 与另一个引擎。
"""
from .detector import OnnxNERDetector

__all__ = ["OnnxNERDetector"]
