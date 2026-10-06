"""ONNX 中文 NER 检测器: 用编码器模型直接输出 span, 无需 llama.cpp。

加载 HF 导出的 `model.onnx` + `tokenizer.json`, 跑 token 分类, 再按 BIO 聚合出实体。
本文件只依赖 `docanon.contract`, 可以整块搬到别的项目里 —— 所以它不认识 PERSON/ORG
这些实体名, 标签映射表必须由调用方传进来。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..contract import Block, Detection, Detector, Span


class OnnxNERDetector(Detector):
    name = "onnx"

    def __init__(
        self,
        model_dir: str | Path,
        entity_map: dict[str, str],
        max_length: int = 510,
    ) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        if not entity_map:
            raise ValueError(
                f"{model_dir}: 必须给出 标签->实体类型 映射表; "
                "空表等于这个模型白跑, 不该静默算作已检测"
            )

        model_dir = Path(model_dir)
        onnx_path = model_dir / "model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"找不到 ONNX 模型: {onnx_path}")

        self.session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self.id2label = {int(k): v for k, v in (cfg.get("id2label") or {}).items()}
        self.entity_map = dict(entity_map)
        self.model_dir = model_dir

    def capabilities(self) -> list[str]:
        return sorted(set(self.entity_map.values()))

    def _logits(self, enc) -> np.ndarray:
        ids = np.array([enc.ids], dtype=np.int64)
        feeds: dict[str, np.ndarray] = {
            "input_ids": ids,
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        feeds = {k: v for k, v in feeds.items() if k in self.input_names}
        return self.session.run(None, feeds)[0]

    def detect(self, block: Block) -> list[Detection]:
        text = block.text
        if not text.strip():
            return []
        enc = self.tokenizer.encode(text)
        preds = self._logits(enc)[0].argmax(-1)

        spans: list[list] = []
        cur: list | None = None
        for i, pid in enumerate(preds):
            if i >= len(enc.offsets):
                break
            start, end = enc.offsets[i]
            if start == end:  # 特殊 token / padding
                continue
            label = self.id2label.get(int(pid), "O")
            tag = label[:2]
            kind = label[2:].lower()
            if tag == "B-":
                if cur:
                    spans.append(cur)
                cur = [kind, start, end]
            elif tag == "I-" and cur and cur[0] == kind:
                cur[2] = max(cur[2], end)
            elif tag == "S-":
                if cur:
                    spans.append(cur)
                    cur = None
                spans.append([kind, start, end])
            else:  # O 或其他
                if cur:
                    spans.append(cur)
                    cur = None
        if cur:
            spans.append(cur)

        out: list[Detection] = []
        for kind, start, end in spans:
            entity_type = self.entity_map.get(kind)
            if not entity_type:
                continue
            start, end = max(0, start), min(len(text), end)
            out.append(
                Detection(
                    span=Span(start, end, text[start:end]),
                    entity_type=entity_type,
                    source="onnx",
                    confidence=0.9,
                )
            )
        return out
