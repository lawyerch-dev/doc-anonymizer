"""检测器包。"""
from ..contract import Detector
from .base import DETECTORS, build_detectors, clear_detector_cache
from .dictionary import DictionaryDetector
from ..engines.onnx_ner import OnnxNERDetector
from .rule import RuleDetector

__all__ = [
    "DETECTORS",
    "Detector",
    "build_detectors",
    "clear_detector_cache",
    "RuleDetector",
    "DictionaryDetector",
    "OnnxNERDetector",
]
