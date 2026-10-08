"""引擎清单: 把实际登记、实际加载得起来的引擎列出来。

存在的意义是"别猜哪层检测在跑": 配置写了 `onnx_ner: true` 不代表模型真的加载成功了。
`docanon engines` 会逐个真去构造并问一次 ready(), 把不行的原因摊开。
"""
from __future__ import annotations

from pathlib import Path

from .detectors import DETECTORS
from .extractors import extractor_classes


def describe_detector(name: str, config) -> list[dict]:
    """构造该引擎并自述; 起不来就如实记下来, 不抛给调用方。"""
    try:
        built = DETECTORS[name](config)
    except Exception as exc:  # noqa: BLE001
        return [{"name": name, "status": f"加载失败: {exc}", "capabilities": []}]
    rows = []
    for d in built:
        reason = d.ready()
        model_dir = getattr(d, "model_dir", None)
        rows.append({
            # 同名引擎可能有多份(两个 ONNX 模型), 不带目录名就分不出谁是谁
            "name": f"{name}({Path(model_dir).name})" if model_dir else name,
            "status": "可用" if reason is None else f"不可用: {reason}",
            "capabilities": d.capabilities(),
        })
    return rows


def list_engines(config) -> list[dict]:
    """当前配置下每个引擎的状态, 外加所有已登记的抽取器。"""
    enabled = config.detectors or {}
    rows = []
    for name in sorted(DETECTORS):
        if not enabled.get(name, False):
            rows.append({"kind": "检测器", "name": name, "status": "配置未启用",
                         "capabilities": []})
            continue
        for r in describe_detector(name, config):
            rows.append({"kind": "检测器", **r})
    for cls in extractor_classes():
        try:
            reason = cls().ready()
        except Exception as exc:  # noqa: BLE001
            reason = f"加载失败: {exc}"
        rows.append({
            "kind": "抽取器", "name": cls.name,
            "status": "已登记" if reason is None else f"不可用: {reason}",
            "capabilities": list(cls.extensions),
        })
    return rows
