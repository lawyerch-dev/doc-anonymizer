"""检测器包。"""
from .base import Detector, build_detectors
from .rule import RuleDetector
from .dictionary import DictionaryDetector

__all__ = ["Detector", "build_detectors", "RuleDetector", "DictionaryDetector"]
