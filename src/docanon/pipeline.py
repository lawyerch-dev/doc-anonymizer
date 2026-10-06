"""编排: 抽取 → 检测 → 合并 → 策略替换 → 回写。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .detectors import build_detectors
from .extractors import build_extractor
from .mapping import MappingStore
from .contract import Block, Detection, ExtractedDoc
from .resolve import resolve_overlaps
from .strategies import apply_spans, replacement_for
from .writers import BlockRedaction, write_output


@dataclass
class ProcessResult:
    source: str
    output_path: str
    entity_counts: dict[str, int] = field(default_factory=dict)
    # 实际写盘的文件(扫描 PDF 每页一张, 故为列表)
    outputs: list[str] = field(default_factory=list)
    # 溯源信息
    extractor: str = ""
    detectors: list[str] = field(default_factory=list)
    detections: list[dict] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)


class EngineError(RuntimeError):
    """检测引擎装不起来或没在应答。"""


def prepare_detectors(config) -> list:
    """构建并体检启用的检测器; 任何一个不起来就整体失败, 一个文件都不写。

    少一层检测器就等于少一类脱敏, 这种文档绝不能被报成「已处理」。
    """
    detectors = build_detectors(config)
    broken = []
    for d in detectors:
        reason = d.ready()
        if reason:
            broken.append(f"{d.name}: {reason}")
    if broken:
        raise EngineError("；".join(broken))
    return detectors


def _detect_block(block: Block, detectors) -> list[Detection]:
    found: list[Detection] = []
    for detector in detectors:
        found.extend(detector.detect(block))
    return resolve_overlaps(found)


def _output_path(path: Path, out_dir: Path, rel: Path | None, ext: str) -> Path:
    """产物路径: 保留源文件相对目录, 文件名带上源扩展名以免同名互相覆盖。

    run ./docs -o ./out 时 docs/子目录/sample.docx -> out/子目录/sample.docx.redacted.txt
    """
    rel = rel or Path(path.name)
    out_path = out_dir / rel.parent / f"{path.name}.redacted{ext}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


_EXT_BY_FORMAT = {"docx": ".docx", "pdf": ".pdf"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def _out_ext(doc: ExtractedDoc, path: Path) -> str:
    fmt = doc.meta.get("format")
    if fmt in _EXT_BY_FORMAT:
        return _EXT_BY_FORMAT[fmt]
    if fmt == "image":
        suf = path.suffix.lower()
        return suf if suf in _IMAGE_EXTS else ".png"
    return path.suffix or ".txt"  # text / table 保持源扩展名


def process_file(
    path: Path, out_dir: Path, config: Config, store: MappingStore,
    rel: Path | None = None,
) -> ProcessResult:
    t0 = time.perf_counter()
    extractor = build_extractor(path)
    doc = extractor.extract(path)
    t_extract = time.perf_counter()
    detectors = build_detectors(config)

    counts: dict[str, int] = {}
    reds: list[BlockRedaction] = []
    detections: list[dict] = []
    for block in doc.blocks:
        repls: list[tuple[int, int, str]] = []
        for det in _detect_block(block, detectors):
            strategy = config.strategy_for(det.entity_type)
            repl = replacement_for(store, det.entity_type, det.span.text, strategy)
            repls.append((det.span.start, det.span.end, repl))
            counts[det.entity_type] = counts.get(det.entity_type, 0) + 1
            detections.append({
                "entity_type": det.entity_type,
                "source": det.source,
                "strategy": strategy,
                "original": det.span.text,
                "replacement": repl,
                "locator": block.locator,
            })
        reds.append(BlockRedaction(block, repls, apply_spans(block.text, repls)))
    t_detect = time.perf_counter()

    det_names: list[str] = []
    for d in detectors:
        if d.name not in det_names:
            det_names.append(d.name)

    out_path = _output_path(path, out_dir, rel, _out_ext(doc, path))
    written = write_output(doc, reds, out_path)
    t_write = time.perf_counter()

    return ProcessResult(
        str(path), written[0] if written else str(out_path), counts, written,
        extractor=extractor.name,
        detectors=det_names,
        detections=detections,
        timing={
            "extract_ms": round((t_extract - t0) * 1000, 1),
            "detect_ms": round((t_detect - t_extract) * 1000, 1),
            "write_ms": round((t_write - t_detect) * 1000, 1),
            "total_ms": round((t_write - t0) * 1000, 1),
        },
    )
