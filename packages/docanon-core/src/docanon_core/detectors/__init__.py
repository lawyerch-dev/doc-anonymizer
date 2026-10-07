"""检测器包。"""
from docanon_contract import Detector
from .base import DETECTORS, build_detectors, clear_detector_cache
from .dictionary import DictionaryDetector
from docanon_engine_ner_onnx import OnnxNERDetector
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
