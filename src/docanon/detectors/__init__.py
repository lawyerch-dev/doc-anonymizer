"""检测器包。"""
from .base import Detector, build_detectors
from .rule import RuleDetector
from .dictionary import DictionaryDetector
from .onnx_ner import OnnxNERDetector

__all__ = ["Detector", "build_detectors", "RuleDetector", "DictionaryDetector", "OnnxNERDetector"]
