"""编排: 抽取 → 检测 → 合并 → 策略替换 → 回写。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .detectors import build_detectors
from .extractors import build_extractor
from .mapping import MappingStore
from .models import Block, Detection, ExtractedDoc
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


def _detect_block(block: Block, detectors) -> list[Detection]:
    found: list[Detection] = []
    for detector in detectors:
        found.extend(detector.detect(block))
    return resolve_overlaps(found)


def _redact_block(block: Block, config: Config, store: MappingStore) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    replacements: list[tuple[int, int, str]] = []
    for det in _detect_block(block, config._detectors):  # type: ignore[attr-defined]
        strategy = config.strategy_for(det.entity_type)
        repl = replacement_for(store, det.entity_type, det.span.text, strategy)
        replacements.append((det.span.start, det.span.end, repl))
        counts[det.entity_type] = counts.get(det.entity_type, 0) + 1
    return apply_spans(block.text, replacements), counts


def _write_text_output(doc: ExtractedDoc, out_path: Path, texts: list[str]) -> None:
    out_path.write_text("\n".join(texts), encoding="utf-8")


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
    extractor = build_extractor(path)
    doc = extractor.extract(path)
    detectors = build_detectors(config)
    config._detectors = detectors  # type: ignore[attr-defined]

    counts: dict[str, int] = {}
    reds: list[BlockRedaction] = []
    for block in doc.blocks:
        repls: list[tuple[int, int, str]] = []
        for det in _detect_block(block, detectors):
            strategy = config.strategy_for(det.entity_type)
            repl = replacement_for(store, det.entity_type, det.span.text, strategy)
            repls.append((det.span.start, det.span.end, repl))
            counts[det.entity_type] = counts.get(det.entity_type, 0) + 1
        reds.append(BlockRedaction(block, repls, apply_spans(block.text, repls)))

    out_path = _output_path(path, out_dir, rel, _out_ext(doc, path))
    written = write_output(doc, reds, out_path)
    return ProcessResult(str(path), written[0] if written else str(out_path), counts, written)
