"""编排: 抽取 → 检测 → 合并 → 策略替换 → 回写。"""
from __future__ import annotations

import hashlib
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .detectors import build_detectors
from .extractors import build_extractor
from .redaction.mapping import MappingStore
from docanon_contract import Block, Detection, ExtractedDoc
from .redaction.resolve import resolve_overlaps
from .redaction.strategies import apply_spans, replacement_for
from .redaction.writers import BlockRedaction, write_output


@dataclass
class ProcessResult:
    source: str
    output_path: str
    entity_counts: dict[str, int] = field(default_factory=dict)
    # 实际写盘的文件(扫描 PDF 每页一张, 故为列表)
    outputs: list[str] = field(default_factory=list)
    # 溯源信息
    extractor: str = ""
    converted_from: str = ""   # 旧格式转换来源(如 ".doc"), 空表示未转换
    output_format: str = ""    # 产物格式(如 "docx"), 空表示与源同格式
    detectors: list[str] = field(default_factory=list)
    detections: list[dict] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)


class EngineError(RuntimeError):
    """检测引擎装不起来或没在应答。"""


class Cancelled(RuntimeError):
    """用户在跑的中途取消了。

    只在**写产物之前**抛(识别阶段查信号) —— 半截产物比没产物更危险, 所以取消就什么都不留。
    """


# 策略 "keep" = 这类命中**不动**。它必须在替换之前拦掉: 没有这个策略, 配置就只能表达
# "抹成什么", 没法表达"别碰它" —— 于是"我只想抹数字型标识、人名机构都留着"这件事写不出来
# (没列出的类型会被 DEFAULT 兜住一起抹掉)。见 configs/legal.yaml。
_KEEP = "keep"


def _tick(progress, stage: str, done: int = 0, total: int = 0) -> None:
    """报一次进度; 没传 progress(CLI / 批任务)就是空操作。"""
    if progress is not None:
        progress(stage, done, total)


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
    return resolve_overlaps(_drop_model_false_positives(block.text, found))


# 模型层的两处实测误伤, 用确定性规则挡掉 —— **不写进提示词**: 试过给 4B 模型加"不要标注…"清单,
# 同一份真合同上它反而漏了 2 处实体(召回从 11/11 掉到 9/11)。提示词会漂, 代码不会。
#
# 1. 《》里装的是法律法规/文件/作品名, 不是隐私实体(实测: 合同里的《民法典》被当机构抹成《**》,
#    法律依据就没了)。2. AMOUNT 必须有"钱的痕迹"(数字 / ¥ / 元/万/亿), 否则不是金额
#    (实测: 期限"十日"被当金额抹掉, 合同期限就没了)。
# 两条都**只管模型层**: rule/dictionary 是精确匹配(用户明确列的词、写死的号码格式), 不该被放过。
_TITLE_RE = re.compile(r"《[^》\n]{1,80}》")
_MONEY_MARK_RE = re.compile(r"[0-9０-９]|[¥￥]|元|万|亿")
_MODEL_SOURCES = frozenset({"llm", "onnx"})


def _drop_model_false_positives(text: str, detections: list[Detection]) -> list[Detection]:
    """把模型层这两类已知误伤丢掉; 不含书名号、也没有模型命中时原样返回(常见路径不做多余计算)。"""
    model = [d for d in detections if d.source in _MODEL_SOURCES]
    if not model:
        return detections
    titles = [(m.start(), m.end()) for m in _TITLE_RE.finditer(text)] if "《" in text else []

    def bad(det: Detection) -> bool:
        if det.source not in _MODEL_SOURCES:
            return False
        if any(lo <= det.span.start and det.span.end <= hi for lo, hi in titles):
            return True
        return det.entity_type == "AMOUNT" and not _MONEY_MARK_RE.search(det.span.text)

    return [d for d in detections if not bad(d)]


# 文件名单段上限: APFS/ext4 都是 255 字节(UTF-8 编码后的字节数, 不含目录段)
_MAX_NAME_BYTES = 255
_NAME_HASH_LEN = 8
_NAME_PREFIX = "【脱敏版】"


def _fit_utf8(text: str, budget: int) -> str:
    """按 UTF-8 字节数截断(整字符截, 不留半个多字节字符)。"""
    raw = text.encode("utf-8")
    if len(raw) <= budget:
        return text
    return raw[:budget].decode("utf-8", errors="ignore")


def _output_path(path: Path, out_dir: Path, rel: Path | None, ext: str) -> Path:
    """产物路径: `【脱敏版】<源文件全名><目标扩展名>`, 保留源文件相对目录。

    run ./docs -o ./out 时 docs/子目录/sample.docx -> out/子目录/【脱敏版】sample.docx

    格式变了才带上源扩展名(.doc -> .docx / .xls -> .xlsx): 不这样, 同目录下 `a.doc` 与 `a.docx`
    会撞成同一个 `【脱敏版】a.docx`, 等于**静默丢一个文件**。命名只由输入决定(不看目录里已有什么),
    否则 `--resume` 与账本记的路径对不上。

    文件名超过文件系统 255 字节上限时确定性截断: 保住扩展名, 源文件名截短后补 `~+短哈希` 防撞名
    —— 哈希只由完整目标名算出, 同一输入永远得到同一个产物名, `--resume`/账本依旧对得上。
    """
    rel = rel or Path(path.name)
    # `path.name` 本身已经带源扩展名, 所以只在"格式变了"时再补目标扩展名
    tail = "" if ext.lower() == path.suffix.lower() else ext
    name = f"{_NAME_PREFIX}{path.name}{tail}"
    if len(name.encode("utf-8")) > _MAX_NAME_BYTES:
        marker = f"~{hashlib.sha256(name.encode('utf-8')).hexdigest()[:_NAME_HASH_LEN]}"
        keep_ext = f"{path.suffix}{tail}"
        stem_budget = (
            _MAX_NAME_BYTES
            - len(_NAME_PREFIX.encode())
            - len(marker.encode())
            - len(keep_ext.encode())
        )
        name = f"{_NAME_PREFIX}{_fit_utf8(path.stem, max(stem_budget, 1))}{marker}{keep_ext}"
    out_path = out_dir / rel.parent / name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


_EXT_BY_FORMAT = {"docx": ".docx", "pdf": ".pdf"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def _out_ext(doc: ExtractedDoc, path: Path) -> str:
    # 抽取器可以显式指定产物后缀(如 .xls -> .xlsx, 否则会回落成源后缀 .xls 骗人)
    explicit = doc.meta.get("out_ext")
    if explicit:
        return explicit
    fmt = doc.meta.get("format")
    if fmt in _EXT_BY_FORMAT:
        return _EXT_BY_FORMAT[fmt]
    if fmt == "image":
        suf = path.suffix.lower()
        return suf if suf in _IMAGE_EXTS else ".png"
    return path.suffix or ".txt"  # text / table 保持源扩展名


def process_file(
    path: Path, out_dir: Path, config: Config, store: MappingStore,
    rel: Path | None = None, progress=None, cancel=None,
) -> ProcessResult:
    """处理一个文件。

    `progress(stage, done, total)` 与 `cancel`(threading.Event) 都是可选的 —— CLI / job 不传就
    和以前一模一样。Web 传进来是为了让那 30 多秒的识别过程能被看见、被中止。
    """
    t0 = time.perf_counter()
    _tick(progress, "extract")
    extractor = build_extractor(path, allow_legacy=config.legacy_convert)
    doc = extractor.extract(path)
    t_extract = time.perf_counter()

    counts: dict[str, int] = {}
    detections: list[dict] = []
    det_names: list[str] = []
    written: list[str] = []
    try:
        detectors = build_detectors(config)
        reds: list[BlockRedaction] = []
        total = len(doc.blocks)
        for index, block in enumerate(doc.blocks, 1):
            if cancel is not None and cancel.is_set():   # 只在写之前查: 取消 = 一个产物都不留
                raise Cancelled("已取消")
            _tick(progress, "detect", index, total)
            repls: list[tuple[int, int, str]] = []
            for det in _detect_block(block, detectors):
                strategy = config.strategy_for(det.entity_type)
                if strategy == _KEEP:
                    # 配置说"这类别动": 只留溯源, 不替换、也不计数(counts 是"实际抹掉了几处")
                    detections.append({
                        "entity_type": det.entity_type,
                        "source": det.source,
                        "strategy": strategy,
                        "original": det.span.text,
                        "replacement": None,
                        "locator": block.locator,
                    })
                    continue
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

        for d in detectors:
            if d.name not in det_names:
                det_names.append(d.name)

        _tick(progress, "write")
        out_path = _output_path(path, out_dir, rel, _out_ext(doc, path))
        written = write_output(doc, reds, out_path)
    finally:
        # 旧格式转换的临时目录在回写(要重开 modern)之后才能删
        workdir = doc.meta.get("_convert_workdir")
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    t_write = time.perf_counter()

    return ProcessResult(
        str(path), written[0] if written else str(out_path), counts, written,
        extractor=extractor.name,
        converted_from=doc.meta.get("converted_from", ""),
        output_format=doc.meta.get("out_ext", "").lstrip("."),
        detectors=det_names,
        detections=detections,
        timing={
            "extract_ms": round((t_extract - t0) * 1000, 1),
            "detect_ms": round((t_detect - t_extract) * 1000, 1),
            "write_ms": round((t_write - t_detect) * 1000, 1),
            "total_ms": round((t_write - t0) * 1000, 1),
        },
    )
