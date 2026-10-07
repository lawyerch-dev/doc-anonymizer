"""检测器注册表与进程级缓存。引擎外形(ABC)在 `docanon.contract`。"""
from __future__ import annotations

from typing import Callable

from .. import resources
from ..contract import Detector


def _build_rule(config) -> list[Detector]:
    from .rule import RuleDetector

    return [RuleDetector()]


def _build_dictionary(config) -> list[Detector]:
    from .dictionary import DictionaryDetector

    return [DictionaryDetector(config.dictionary)]


def _build_onnx(config) -> list[Detector]:
    from ..engines.onnx_ner import OnnxNERDetector

    # 模型目录写在配置里, 是相对资源根的路径(不是调用者的 cwd), 打包后同样成立
    return [
        OnnxNERDetector(resources.resolve(model_dir), config.onnx.entity_map)
        for model_dir in config.onnx.model_dirs
    ]


def _build_llm(config) -> list[Detector]:
    from ..engines.llm.ner import LLMNERDetector

    return [LLMNERDetector(config.llm)]


# 加新引擎: 在这里登记一行, 配置文件里用同名键 true 打开。
DETECTORS: dict[str, Callable[[object], list[Detector]]] = {
    "rule": _build_rule,
    "dictionary": _build_dictionary,
    "onnx_ner": _build_onnx,
    "llm_ner": _build_llm,
}

# ONNX session / tokenizer 加载一次约 0.5s, 逐文件重建会把整批跑慢一倍以上,
# 所以按配置指纹缓存。缓存的实例会被 ThreadingHTTPServer 的多个请求共用,
# 现有检测器要么无状态, 要么(ONNX/OCR)底层本身就是线程安全的进程级会话。
_cache: dict[tuple, list[Detector]] = {}


def _fingerprint(config) -> tuple:
    return (
        tuple(sorted((k, bool(v)) for k, v in (config.detectors or {}).items())),
        tuple(config.onnx.model_dirs),
        tuple(sorted((config.onnx.entity_map or {}).items())),
        (
            config.llm.base_url,
            config.llm.model,
            config.llm.timeout,
            config.llm.chunk_size,
            config.llm.disable_thinking,
        ),
    )


def build_detectors(config) -> list[Detector]:
    """返回配置启用的检测器; 同一份配置在整个进程里只真正加载一次。"""
    enabled = config.detectors or {}
    unknown = sorted(k for k, v in enabled.items() if v and k not in DETECTORS)
    if unknown:
        raise ValueError(
            f"配置里有未知的检测器: {', '.join(unknown)}"
            f"（已登记: {', '.join(DETECTORS)}）"
        )
    chosen = [name for name in DETECTORS if enabled.get(name, False)]
    if not chosen:
        raise ValueError(
            "配置里没有任何启用的检测器; 什么都不检测就不能产出「已脱敏」的文件"
        )

    key = _fingerprint(config)
    detectors = _cache.get(key)
    if detectors is None:
        detectors = []
        for name in chosen:
            detectors.extend(DETECTORS[name](config))
        _cache[key] = detectors
    return detectors


def clear_detector_cache() -> None:
    """测试用: 清掉进程级缓存。"""
    _cache.clear()
