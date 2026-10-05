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


def _write_image_output(doc: ExtractedDoc, out_path: Path, hit_bboxes: list[tuple]) -> list[str]:
    """对图片/扫描页涂黑命中的文字行 bbox, 返回实际写出的文件。"""
    from PIL import ImageDraw, Image  # type: ignore

    if "needs_image_redaction" in doc.meta and doc.meta.get("_scanned_images"):
        # PDF 扫描页: 每页一张 PNG
        by_page: dict[int, list[tuple]] = {}
        for page, bbox in hit_bboxes:
            by_page.setdefault(page, []).append(bbox)
        written: list[str] = []
        for item in doc.meta["_scanned_images"]:
            img = item["image"]
            draw = ImageDraw.Draw(img)
            for bbox in by_page.get(item["page"], []):
                draw.rectangle(bbox, fill="black")
            page_path = out_path.with_name(f"{out_path.stem}.p{item['page']}.png")
            img.save(page_path)
            written.append(str(page_path))
        return written

    # 单张图片
    img = Image.open(doc.image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for _, bbox in hit_bboxes:
        draw.rectangle(bbox, fill="black")
    img.save(out_path)
    return [str(out_path)]


def process_file(
    path: Path, out_dir: Path, config: Config, store: MappingStore,
    rel: Path | None = None,
) -> ProcessResult:
    extractor = build_extractor(path)
    doc = extractor.extract(path)
    detectors = build_detectors(config)
    config._detectors = detectors  # type: ignore[attr-defined]

    counts: dict[str, int] = {}
    hit_bboxes: list[tuple] = []

    if doc.meta.get("needs_image_redaction"):
        for block in doc.blocks:
            new_text, c = _redact_block(block, config, store)
            for k, v in c.items():
                counts[k] = counts.get(k, 0) + v
            if new_text != block.text:  # 命中, 涂黑该行
                page = block.locator.get("page", 0)
                hit_bboxes.append((page, tuple(block.locator["bbox"])))
        out_path = _output_path(path, out_dir, rel, ".png")
        written = _write_image_output(doc, out_path, hit_bboxes)
        return ProcessResult(str(path), written[0] if written else str(out_path), counts, written)

    # 文本类
    texts: list[str] = []
    for block in doc.blocks:
        new_text, c = _redact_block(block, config, store)
        texts.append(new_text)
        for k, v in c.items():
            counts[k] = counts.get(k, 0) + v
    out_path = _output_path(path, out_dir, rel, ".txt")
    _write_text_output(doc, out_path, texts)
    return ProcessResult(str(path), str(out_path), counts, [str(out_path)])
