# 旧版 Office 自动转换（.doc/.xls/.wps）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `.doc/.xls/.wps` 经 LibreOffice 自动转成 `.docx/.xlsx` 后照常脱敏，并在账本/界面显式标注"产物已转换"。

**Architecture:** 转换放在**抽取层**：core 新增 `convert.py`（定位 soffice + headless 转换）与 `LegacyOfficeExtractor`（转换后委托现有 `DocxExtractor`/`TableExtractor`）。回写重开 `doc.source_path`，故只需把 `source_path` 指到转换后的现代文件，原格式回写逻辑零改动。soffice 走"系统优先 → `var/libreoffice/`"，不进包。

**Tech Stack:** Python 3.12（stdlib `subprocess`/`shutil`/`tempfile`）、python-docx、openpyxl、pytest、bash（获取脚本）。

**Spec:** `docs/specs/2026-10-08-legacy-office-conversion-design.md`

## Global Constraints

- 引擎只依赖 `docanon_contract` + 自己；core 只用引擎公开面（`tests/test_architecture.py` 锁死）。
- 布局只有一处真相：`resources.LAYOUT`（`packages/docanon-core/tests/test_layout.py` 锁死）。
- 少于一层就报错，绝不静默给空结果；没产出脱敏结果的条目必须标成未处理。
- 文档一源一址；改现状文档要同步 `.en` 版并跑 `python3 website/scripts/sync-content.py --record-hashes`。
- 加/删测试后同步根 `AGENTS.md` 的「（N 项，约 M 秒）」计数（`tests/test_docs.py` 锁死）。
- 计划里的提交步骤：在本项目**需先经用户同意**才真正 `git commit`（用户规则）。

## Review Focus

- **`.xls` 的产物扩展名**：源 `.xls` 必须产出 `….xls.redacted.xlsx`，内容为 xlsx（否则扩展名骗人）。→ T4 测试。
- **无 soffice 时的回落**：`.doc` 不能报成功、不能炸整轮，要记 `unsupported` 且带可操作 reason。→ T5 测试。
- **转换失败/源损坏**：记 `error` 且 `error` 非空，退出码非 0。→ T4/T5 测试。
- **`legacy_convert=false`**：必须回到旧行为（一律 `unsupported`），不残留转换。→ T6 测试。
- **临时目录泄漏**：转换产物在回写后被清理（`finally`）。→ T4 测试。
- **同 .docx 的既有局限**（页眉/页脚/表格/文本框不在 `iter_paragraphs` 内）：本改动**不引入也不修复**，行为与 `.docx` 对齐，仅记录。

---

### Task 1: 文档守卫放行 agent 工作文档 + 登记设计文档

**Files:**
- Modify: `tests/test_docs.py`（`GENERATED_PARTS` 与 `RECORDS`）
- Test: `tests/test_docs.py`

**Interfaces:**
- Produces: 之后所有任务可安全把计划/设计文档留在仓库而不触发文档漂移红灯。

- [ ] **Step 1: 写失败断言（先证明守卫会拦）**

在 `tests/test_docs.py` 末尾临时加一条测试，断言 `docs/superpowers/` 下的 md 不在 `CURRENT_DOCS`：

```python
def test_agent_working_docs_are_not_doc_guarded():
    assert not any("superpowers" in p.parts for p in CURRENT_DOCS), \
        "agent 工作文档(计划/规格)不该进文档漂移守卫"
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest tests/test_docs.py::test_agent_working_docs_are_not_doc_guarded -q`
Expected: FAIL（`docs/superpowers/plans/…` 已存在，当前被列入 `CURRENT_DOCS`）

- [ ] **Step 3: 实现——放行 + 登记**

改 `tests/test_docs.py`：

```python
GENERATED_PARTS = ("node_modules", ".astro", "dist", "out", "superpowers")
```

```python
RECORDS = [
    REPO / "docs" / "specs" / "2026-10-05-doc-anonymizer-design.md",
    REPO / "docs" / "specs" / "2026-10-08-legacy-office-conversion-design.md",
    REPO / "CHANGELOG.md",
]
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest tests/test_docs.py -q`
Expected: PASS（设计文档在 RECORDS，计划在 superpowers 放行区）

- [ ] **Step 5: Commit**

```bash
git add tests/test_docs.py docs/specs/2026-10-08-legacy-office-conversion-design.md docs/superpowers/plans/2026-10-08-legacy-office-conversion.md
git commit -m "docs: 登记旧格式转换设计文档, agent 工作文档移出文档守卫"
```

---

### Task 2: LAYOUT 增加 libreoffice 资源项

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/resources.py:25-32`（`LAYOUT`）
- Modify: `packages/docanon-core/tests/test_layout.py:20-25`
- Test: `packages/docanon-core/tests/test_layout.py`

**Interfaces:**
- Produces: `resources.path("libreoffice")` / `resources.libreoffice_dir() -> Path`。

- [ ] **Step 1: 写失败测试**

在 `test_layout.py::test_accessors_go_through_the_layout_table` 内加：

```python
    assert resources.libreoffice_dir() == resources.path("libreoffice")
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_layout.py::test_accessors_go_through_the_layout_table -q`
Expected: FAIL（`AttributeError: … libreoffice_dir`）

- [ ] **Step 3: 实现**

`resources.py` 的 `LAYOUT` 增加一项：

```python
    "libreoffice": "var/libreoffice",   # 旧版 Office 转换用(可选, fetch_libreoffice.sh 下载)
```

并在 `models_dir()` 之后加访问器：

```python
def libreoffice_dir() -> Path:
    return path("libreoffice")
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_layout.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/docanon-core/src/docanon_core/resources.py packages/docanon-core/tests/test_layout.py
git commit -m "feat(resources): LAYOUT 增加 libreoffice 资源项"
```

---

### Task 3: convert.py —— soffice 定位与 headless 转换

**Files:**
- Create: `packages/docanon-core/src/docanon_core/convert.py`
- Test: `packages/docanon-core/tests/test_convert.py`

**Interfaces:**
- Produces:
  - `TARGETS: dict[str, tuple[str, str]]`（源后缀 → (soffice 目标格式, 产物后缀)）
  - `LEGACY_EXTENSIONS: tuple[str, ...]`
  - `find_soffice() -> Path | None`
  - `unavailable_reason() -> str | None`（可用返回 `None`）
  - `to_modern(src: Path, workdir: Path) -> tuple[Path, str]`（返回 (产物路径, 产物后缀)）
- Consumes: `resources.path("libreoffice")`（Task 2）

- [ ] **Step 1: 写失败测试**

创建 `packages/docanon-core/tests/test_convert.py`：

```python
"""soffice 定位与转换: 用假 soffice 脚本保证离线可测。"""
from __future__ import annotations

from pathlib import Path

import pytest

from docanon_core import convert


def _fake_soffice(tmp_path: Path) -> Path:
    """造一个假 soffice: 把 FIXTURE_DIR/<fmt> 拷成 <src stem>.<fmt>。"""
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    (fixture / "docx").write_bytes(b"PK\x03\x04 fake-docx")
    (fixture / "xlsx").write_bytes(b"PK\x03\x04 fake-xlsx")
    stub = tmp_path / "soffice"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'outdir=""; fmt=""\n'
        'while [ $# -gt 0 ]; do case "$1" in\n'
        '  --convert-to) fmt="$2"; shift 2;;\n'
        '  --outdir) outdir="$2"; shift 2;;\n'
        '  --headless|--norestore) shift;;\n'
        '  *) src="$1"; shift;;\n'
        "esac; done\n"
        'stem="$(basename "$src")"; stem="${stem%.*}"\n'
        'cp "$FIXTURE_DIR/$fmt" "$outdir/$stem.$fmt"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def test_find_soffice_prefers_env(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    assert convert.find_soffice() == stub


def test_find_soffice_none_when_nothing(monkeypatch):
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    assert convert.find_soffice() is None
    assert "LibreOffice" in convert.unavailable_reason()


def test_to_modern_docx(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    work = tmp_path / "work"
    work.mkdir()

    out, ext = convert.to_modern(src, work)

    assert ext == ".docx"
    assert out.name == "合同.docx"
    assert out.read_bytes().startswith(b"PK")


def test_to_modern_rejects_unknown_suffix(tmp_path):
    with pytest.raises(RuntimeError, match="不是可转换"):
        convert.to_modern(tmp_path / "a.txt", tmp_path)
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_convert.py -q`
Expected: FAIL（`ModuleNotFoundError: docanon_core.convert`）

- [ ] **Step 3: 实现**

创建 `convert.py`：

```python
"""旧版二进制 Office(.doc/.xls/.wps) -> 现代格式(.docx/.xlsx), 借 LibreOffice headless。

这不是"引擎": 它不产出 Block, 只把文件换个格式; 抽取由被委托的抽取器完成。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import resources

# 源后缀 -> (soffice --convert-to 目标格式, 产物后缀)
TARGETS: dict[str, tuple[str, str]] = {
    ".doc": ("docx", ".docx"),
    ".wps": ("docx", ".docx"),
    ".xls": ("xlsx", ".xlsx"),
}
LEGACY_EXTENSIONS: tuple[str, ...] = tuple(TARGETS)

_CONVERT_TIMEOUT = 120
_MAC_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def find_soffice() -> Path | None:
    """按 环境变量 > 系统安装 > var/libreoffice(下载) 的顺序找 soffice。"""
    override = os.environ.get("DOCANON_SOFFICE")
    if override:
        p = Path(override).expanduser()
        return p if p.is_file() else None
    found = shutil.which("soffice")
    if found:
        return Path(found)
    if _MAC_SOFFICE.is_file():
        return _MAC_SOFFICE
    bundled = resources.path("libreoffice")
    if bundled.is_dir():
        hits = sorted(bundled.rglob("soffice"))
        if hits:
            return hits[0]
    return None


def unavailable_reason() -> str | None:
    """可用返回 None; 否则给可操作的缺失原因。"""
    if find_soffice() is None:
        return (
            "缺 LibreOffice(soffice): 装一个, 或运行 ./scripts/fetch_libreoffice.sh, "
            "或设 DOCANON_SOFFICE 指向它"
        )
    return None


def to_modern(src: Path, workdir: Path) -> tuple[Path, str]:
    """把 src 转成现代格式, 返回 (产物路径, 产物后缀)。失败抛 RuntimeError。"""
    suffix = src.suffix.lower()
    try:
        target, out_ext = TARGETS[suffix]
    except KeyError:
        raise RuntimeError(f"不是可转换的旧格式: {src.suffix or '无扩展名'}") from None
    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(unavailable_reason())
    before = {p.name for p in workdir.glob("*")}
    proc = subprocess.run(
        [str(soffice), "--headless", "--norestore",
         "--convert-to", target, "--outdir", str(workdir), str(src)],
        capture_output=True, text=True, timeout=_CONVERT_TIMEOUT,
    )
    produced = [p for p in workdir.glob("*") if p.name not in before]
    if proc.returncode != 0 or not produced:
        detail = (proc.stderr or proc.stdout or "无输出").strip()
        raise RuntimeError(f"LibreOffice 转换失败({suffix} -> {target}): {detail[:200]}")
    return produced[0], out_ext
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_convert.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/docanon-core/src/docanon_core/convert.py packages/docanon-core/tests/test_convert.py
git commit -m "feat(core): 新增 convert.py(soffice 定位与 headless 转换)"
```

---

### Task 4: LegacyOfficeExtractor + 注册 + 产物后缀/临时目录

**Files:**
- Create: `packages/docanon-core/src/docanon_core/extractors/legacy_office.py`
- Modify: `packages/docanon-core/src/docanon_core/extractors/base.py:9-29`
- Modify: `packages/docanon-core/src/docanon_core/extractors/__init__.py`
- Modify: `packages/docanon-core/src/docanon_core/pipeline.py:80-152`（`_out_ext` + `process_file` + `ProcessResult`）
- Modify: `packages/docanon-core/src/docanon_core/config.py:46-53`（加 `legacy_convert: bool = True` 字段, yaml 读取在 Task 6）
- Test: `packages/docanon-core/tests/test_legacy_office.py`

**Interfaces:**
- Consumes: `convert.to_modern`、`convert.LEGACY_EXTENSIONS`（Task 3）
- Produces:
  - `LegacyOfficeExtractor`（`name="legacy_office"`，`extensions=convert.LEGACY_EXTENSIONS`，`ready()` 委托 `convert.unavailable_reason()`）
  - `build_extractor(path, *, allow_legacy: bool = True)`
  - `ProcessResult.converted_from: str`、`ProcessResult.output_format: str`
  - `ExtractedDoc.meta` 约定键：`out_ext` / `converted_from` / `_convert_workdir`

- [ ] **Step 1: 写失败测试**

创建 `packages/docanon-core/tests/test_legacy_office.py`（复用 Task 3 的假 soffice 思路）：

```python
"""旧格式端到端: 转换 -> 抽取 -> 脱敏 -> 回写为现代格式。"""
from __future__ import annotations

from pathlib import Path

from docx import Document

from docanon_core import convert
from docanon_core.config import Config
from docanon_core.pipeline import process_file
from docanon_core.redaction.mapping import MappingStore


def _fake_soffice(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixtures"
    fixture.mkdir()
    d = Document()
    d.add_paragraph("甲方 张三 13812340000")
    d.save(str(fixture / "docx"))
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active["A1"] = "张三 13812340000"
    wb.save(str(fixture / "xlsx"))
    stub = tmp_path / "soffice"
    stub.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'outdir=""; fmt=""\n'
        'while [ $# -gt 0 ]; do case "$1" in\n'
        '  --convert-to) fmt="$2"; shift 2;;\n'
        '  --outdir) outdir="$2"; shift 2;;\n'
        '  --headless|--norestore) shift;;\n'
        '  *) src="$1"; shift;;\n'
        "esac; done\n"
        'stem="$(basename "$src")"; stem="${stem%.*}"\n'
        'cp "$FIXTURE_DIR/$fmt" "$outdir/$stem.$fmt"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def test_doc_becomes_redacted_docx(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    src = tmp_path / "合同.doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"
    out.mkdir()

    res = process_file(src, out, Config(), MappingStore())

    assert res.converted_from == ".doc"
    assert res.output_format == "docx"
    produced = Path(res.output_path)
    assert produced.name == "合同.doc.redacted.docx"
    text = "\n".join(p.text for p in Document(str(produced)).paragraphs)
    assert "13812340000" not in text and "张三" not in text


def test_temp_workdir_is_cleaned(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    import docanon_core.convert as convert_mod
    captured: list[str] = []
    real = convert_mod.tempfile.mkdtemp
    monkeypatch.setattr(convert_mod.tempfile, "mkdtemp",
                        lambda **kw: captured.append(real(**kw)) or captured[-1])
    src = tmp_path / "合同.doc"; src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"; out.mkdir()

    process_file(src, out, Config(), MappingStore())

    assert captured and not Path(captured[-1]).exists(), "转换临时目录必须被清理"


def test_xls_keeps_xlsx_extension(tmp_path, monkeypatch):
    stub = _fake_soffice(tmp_path)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(tmp_path / "fixtures"))
    src = tmp_path / "表.xls"
    src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"; out.mkdir()

    res = process_file(src, out, Config(), MappingStore())

    assert res.output_format == "xlsx"
    assert Path(res.output_path).name == "表.xls.redacted.xlsx"
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_legacy_office.py -q`
Expected: FAIL（`docanon_core.extractors.legacy_office` 不存在 / 未注册）

- [ ] **Step 3: 实现**

创建 `packages/docanon-core/src/docanon_core/extractors/legacy_office.py`：

```python
"""旧版二进制 Office 抽取: 先转成 .docx/.xlsx, 再委托现代抽取器。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from docanon_contract import ExtractedDoc, Extractor

from .. import convert


class LegacyOfficeExtractor(Extractor):
    name = "legacy_office"
    extensions = convert.LEGACY_EXTENSIONS

    def ready(self) -> str | None:
        return convert.unavailable_reason()

    def extract(self, path: Path) -> ExtractedDoc:
        from .table import TableExtractor
        from .text_file import DocxExtractor

        workdir = Path(tempfile.mkdtemp(prefix="docanon-convert-"))
        modern, out_ext = convert.to_modern(path, workdir)
        doc = (DocxExtractor() if out_ext == ".docx" else TableExtractor()).extract(modern)
        doc.meta["converted_from"] = path.suffix.lower()
        doc.meta["out_ext"] = out_ext
        # 回写还要重开 modern, 所以临时目录留到 process_file 收尾再删
        doc.meta["_convert_workdir"] = str(workdir)
        return doc
```

`extractors/base.py`：注册（放在 PDF 之后、文本之前无关紧要，因扩展名不重叠）：

```python
def extractor_classes() -> tuple[type[Extractor], ...]:
    from docanon_engine_ocr import ImageExtractor
    from .pdf import PDFExtractor
    from .table import TableExtractor
    from .text_file import DocxExtractor, TextFileExtractor
    from .legacy_office import LegacyOfficeExtractor

    return (PDFExtractor, TextFileExtractor, DocxExtractor, TableExtractor,
            LegacyOfficeExtractor, ImageExtractor)


def build_extractor(path: Path, *, allow_legacy: bool = True) -> Extractor:
    for cls in extractor_classes():
        if not allow_legacy and cls.name == "legacy_office":
            continue
        extractor = cls()
        if extractor.supports(path):
            return extractor
    raise ValueError(f"不支持的文件类型: {path.suffix or '无扩展名'} ({path})")
```

`extractors/__init__.py`：导出 `LegacyOfficeExtractor`（加入 import 与 `__all__`）。

`pipeline.py`：
- `ProcessResult` 增字段：
```python
    extractor: str = ""
    converted_from: str = ""   # 旧格式转换来源(如 ".doc"), 空表示未转换
    output_format: str = ""    # 产物格式(如 "docx"), 供账本标注
```
- `_out_ext` 优先读显式后缀：
```python
def _out_ext(doc: ExtractedDoc, path: Path) -> str:
    explicit = doc.meta.get("out_ext")
    if explicit:
        return explicit
    fmt = doc.meta.get("format")
    ...
```
- `process_file`：`build_extractor(path, allow_legacy=config.legacy_convert)`；把抽取之后的整段逻辑包进 `try:`，`finally:` 清理：
```python
import shutil  # 顶部

def process_file(path, out_dir, config, store, rel=None):
    t0 = time.perf_counter()
    extractor = build_extractor(path, allow_legacy=config.legacy_convert)
    doc = extractor.extract(path)
    try:
        t_extract = time.perf_counter()
        detectors = build_detectors(config)
        ...  # 现有的检测/替换逻辑不变
        out_path = _output_path(path, out_dir, rel, _out_ext(doc, path))
        written = write_output(doc, reds, out_path)
    finally:
        workdir = doc.meta.get("_convert_workdir")
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
    t_write = time.perf_counter()
    return ProcessResult(
        str(path), written[0] if written else str(out_path), counts, written,
        extractor=extractor.name,
        converted_from=doc.meta.get("converted_from", ""),
        output_format=doc.meta.get("out_ext", "").lstrip("."),
        detectors=det_names, detections=detections,
        timing={...},
    )
```

> 注：`Config` 目前没有 `legacy_convert` 字段，本步先给 `Config` 加 `legacy_convert: bool = True` 默认字段（完整读配置在 Task 6）。加字段后本任务的测试即可跑通。

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_legacy_office.py packages/docanon-core/tests/test_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/docanon-core/src/docanon_core/extractors/ packages/docanon-core/src/docanon_core/pipeline.py packages/docanon-core/src/docanon_core/config.py packages/docanon-core/tests/test_legacy_office.py
git commit -m "feat(core): LegacyOfficeExtractor 自动转换 .doc/.xls/.wps"
```

---

### Task 5: CLI/账本集成与"无 soffice"回落

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/cli.py:12-13,19-32,60-89`
- Modify: `packages/docanon-core/src/docanon_core/job.py:113-123`
- Modify: `packages/docanon-core/tests/test_output_layout.py:57-98`
- Test: `packages/docanon-core/tests/test_output_layout.py`

**Interfaces:**
- Consumes: `ProcessResult.converted_from` / `output_format`（Task 4）、`convert.LEGACY_EXTENSIONS` / `unavailable_reason`
- Produces: CLI 把旧格式纳入 `SUPPORTED`（受 `config.legacy_convert` 门控）；账本条目带 `source_suffix`/`output_format`/`converted`；无 soffice 时记 `unsupported` + `reason`。

- [ ] **Step 1: 写失败测试**

改 `test_output_layout.py`：把两个用 `.doc`（现在是**可转换**格式）的用例换成**真不支持**的扩展名（如 `.zip`），并新增转换用例：

```python
def test_manifest_lists_unsupported_files(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "说明.txt").write_text("张三 13812340000\n", encoding="utf-8")
    (src / "归档.zip").write_bytes(b"PK\x03\x04not office")
    (src / ".DS_Store").write_bytes(b"\x00\x01")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entries = {e["source"]: e for e in _manifest(out)["files"]}
    assert entries["说明.txt"]["status"] == "ok"
    assert entries["归档.zip"]["status"] == "unsupported"
    assert ".DS_Store" not in entries
    assert code != 0


def test_explicit_unsupported_file_is_reported(tmp_path):
    z = tmp_path / "归档.zip"; z.write_bytes(b"PK\x03\x04not office")
    out = tmp_path / "out"

    code = main(["run", str(z), "-o", str(out)])

    assert _manifest(out)["files"] == [
        {"source": "归档.zip", "status": "unsupported", "suffix": ".zip"}
    ]
    assert code != 0
```

新增（假 soffice，端到端）：

```python
def test_doc_converted_and_labelled(tmp_path, monkeypatch):
    import docx
    from _soffice_stub import install_fake_soffice  # 见 Step 3

    fixtures = install_fake_soffice(tmp_path, monkeypatch)
    src = tmp_path / "合同.doc"; src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "ok"
    assert entry["source"] == "合同.doc"
    assert entry["source_suffix"] == ".doc"
    assert entry["output_format"] == "docx"
    assert entry["converted"] is True
    assert (out / "合同.doc.redacted.docx").is_file()
    assert code == 0


def test_doc_without_soffice_is_unsupported(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCANON_SOFFICE", "/no/such/soffice")
    monkeypatch.setattr("docanon_core.convert.find_soffice", lambda: None)
    src = tmp_path / "合同.doc"; src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out)])

    entry = _manifest(out)["files"][0]
    assert entry["status"] == "unsupported"
    assert "LibreOffice" in entry.get("reason", "")
    assert code != 0
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_output_layout.py -q`
Expected: FAIL（`.doc` 现在被当可转换处理 / 缺 `source_suffix` 等）

- [ ] **Step 3: 实现**

新建 `packages/docanon-core/tests/_soffice_stub.py`（货架式测试助手）：

```python
"""测试用的假 soffice: 把预置的 docx/xlsx 拷成目标名, 让转换离线可测。"""
from __future__ import annotations

from pathlib import Path

from docx import Document
import openpyxl


def install_fake_soffice(tmp_path: Path, monkeypatch) -> Path:
    fixture = tmp_path / "fixtures"; fixture.mkdir()
    d = Document(); d.add_paragraph("甲方 张三 13812340000")
    d.save(str(fixture / "docx"))
    wb = openpyxl.Workbook(); wb.active["A1"] = "张三 13812340000"
    wb.save(str(fixture / "xlsx"))
    stub = tmp_path / "soffice"
    stub.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'outdir=""; fmt=""\n'
        'while [ $# -gt 0 ]; do case "$1" in\n'
        '  --convert-to) fmt="$2"; shift 2;;\n'
        '  --outdir) outdir="$2"; shift 2;;\n'
        '  --headless|--norestore) shift;;\n'
        '  *) src="$1"; shift;;\n'
        "esac; done\n"
        'stem="$(basename "$src")"; stem="${stem%.*}"\n'
        'cp "$FIXTURE_DIR/$fmt" "$outdir/$stem.$fmt"\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    monkeypatch.setenv("DOCANON_SOFFICE", str(stub))
    monkeypatch.setenv("FIXTURE_DIR", str(fixture))
    return fixture
```

`cli.py`：

```python
from . import convert

SUPPORTED = {".txt", ".md", ".markdown", ".text", ".docx", ".pdf", ".xlsx", ".csv",
             ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def _collect(target: Path, config) -> tuple[list[Path], list[Path], Path]:
    ...
    supported_ext = SUPPORTED | (set(convert.LEGACY_EXTENSIONS) if config.legacy_convert else set())
    supported = [p for p in files if p.suffix.lower() in supported_ext]
    unsupported = [p for p in files if p.suffix.lower() not in supported_ext]
    return supported, unsupported, base
```

`cmd_run`：调用处改成 `_collect(target, config)`；在 `for path in unsupported` 之前，把"旧格式但缺 soffice"的文件单列：

```python
    legacy = [p for p in supported if p.suffix.lower() in convert.LEGACY_EXTENSIONS]
    legacy_blocked = convert.unavailable_reason() if legacy else None
    ...
    for path in supported:
        rel = path.relative_to(base)
        if legacy_blocked and path.suffix.lower() in convert.LEGACY_EXTENSIONS:
            job.record(str(rel), {"source": str(rel), "status": "unsupported",
                                  "suffix": path.suffix, "reason": legacy_blocked})
            print(f"[…] 跳过(缺 LibreOffice) {rel}: {legacy_blocked}", file=sys.stderr)
            continue
        ...  # 原有处理
```

并在 `entry["status"] == "ok"` 分支里加标注打印：

```python
            if entry.get("converted"):
                print(f"[{index}/{total}] 完成 {rel}  已由 {entry['source_suffix']} 转换, 版式可能被重排", flush=True)
```

`job.py::run_file`：

```python
    def run_file(self, path: Path, rel: Path) -> dict:
        try:
            res = process_file(path, self.out_dir, self.config, self.store, rel=rel)
        except Exception as exc:  # noqa: BLE001
            return {"source": str(rel), "status": "error", "error": str(exc)}
        entry = {"source": str(rel), "status": "ok",
                 "outputs": res.outputs, "counts": res.entity_counts}
        if res.converted_from:
            entry.update(source_suffix=res.converted_from,
                         output_format=res.output_format, converted=True)
        return entry
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_output_layout.py packages/docanon-core/tests/test_job.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/docanon-core/src/docanon_core/cli.py packages/docanon-core/src/docanon_core/job.py packages/docanon-core/tests/test_output_layout.py packages/docanon-core/tests/_soffice_stub.py
git commit -m "feat(cli): 旧格式入 Supported + 账本标注 + 缺 soffice 回落 unsupported"
```

---

### Task 6: config.legacy_convert 可关闭

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/config.py:46-96`
- Modify: `configs/default.yaml`
- Modify: `packages/docanon-core/tests/test_output_layout.py`（新增关闭用例）
- Test: `packages/docanon-core/tests/test_output_layout.py`

**Interfaces:**
- Consumes: Task 4 的 `Config.legacy_convert` 默认字段、Task 5 的 `_collect(config)`
- Produces: `legacy_convert: false` 时 `.doc` 一律 `unsupported`（旧行为）。

- [ ] **Step 1: 写失败测试**

```python
def test_legacy_convert_off_treats_doc_as_unsupported(tmp_path, monkeypatch):
    from _soffice_stub import install_fake_soffice
    install_fake_soffice(tmp_path, monkeypatch)
    (tmp_path / "cfg.yaml").write_text("legacy_convert: false\ndetectors:\n  rule: true\n  dictionary: true\n", encoding="utf-8")
    src = tmp_path / "合同.doc"; src.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    out = tmp_path / "out"

    code = main(["run", str(src), "-o", str(out), "-c", str(tmp_path / "cfg.yaml")])

    assert _manifest(out)["files"][0]["status"] == "unsupported"
    assert code != 0
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_output_layout.py::test_legacy_convert_off_treats_doc_as_unsupported -q`
Expected: FAIL（`legacy_convert` 未从 yaml 读取，仍为 True → 变成 ok）

- [ ] **Step 3: 实现**

`config.py`：`Config` 加字段并在 `load_config` 读取：

```python
@dataclass
class Config:
    strategies: dict[str, str] = field(default_factory=dict)
    dictionary: list[str] = field(default_factory=list)
    detectors: dict[str, bool] = field(default_factory=dict)
    legacy_convert: bool = True
    llm: LLMConfig = field(default_factory=LLMConfig)
    ...

    return Config(
        strategies=...,
        dictionary=...,
        detectors=...,
        legacy_convert=bool(data.get("legacy_convert", True)),
        llm=...,
        ...
    )
```

`configs/default.yaml`：在 `detectors` 之前加

```yaml
# 旧版 Office(.doc/.xls/.wps) 自动转成 .docx/.xlsx 再脱敏(需 LibreOffice); 关掉则一律视为不支持
legacy_convert: true
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_output_layout.py packages/docanon-core/tests/test_legal_preset.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/docanon-core/src/docanon_core/config.py configs/default.yaml packages/docanon-core/tests/test_output_layout.py
git commit -m "feat(config): legacy_convert 开关(默认开)"
```

---

### Task 7: 获取脚本 + doctor + engines 自述

**Files:**
- Create: `scripts/fetch_libreoffice.sh`
- Modify: `scripts/dev.sh:151-199`（`cmd_doctor`）
- Modify: `packages/docanon-core/src/docanon_core/inventory.py:44-46`（抽取器 ready 自述）
- Test: `packages/docanon-core/tests/test_engines.py`

**Interfaces:**
- Consumes: `convert.unavailable_reason()`、`resources.libreoffice_dir()`
- Produces: `docanon engines` 里 `legacy_office` 行显示可用/不可用原因；`doctor` 报 soffice 来源。

- [ ] **Step 1: 写失败测试**

在 `test_engines.py` 加：

```python
def test_engines_reports_legacy_office_status(monkeypatch):
    from docanon_core import inventory
    from docanon_core.config import Config

    monkeypatch.setattr("docanon_core.convert.find_soffice", lambda: None)
    rows = {r["name"]: r for r in inventory.list_engines(Config(detectors={}))}
    assert rows["legacy_office"]["status"].startswith("不可用")
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_engines.py::test_engines_reports_legacy_office_status -q`
Expected: FAIL（抽取器行固定为"已登记"，不调 ready()）

- [ ] **Step 3: 实现**

`inventory.py` 抽取器段：

```python
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
```

新建 `scripts/fetch_libreoffice.sh`：

```bash
#!/usr/bin/env bash
# 取 LibreOffice 到 var/libreoffice/(不进包; 与 file-viewer/模型同模式)。
# 用法: ./scripts/fetch_libreoffice.sh [版本]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-25.2.5}"
DEST="$ROOT/var/libreoffice"
mkdir -p "$DEST"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
os="$(uname -s)"; arch="$(uname -m)"
case "$os" in
  Darwin)
    url="https://download.documentfoundation.org/libreoffice/stable/${VER}/mac/aarch64/LibreOffice_${VER}_MacOS_aarch64.dmg"
    [ "$arch" = "aarch64" ] || url="https://download.documentfoundation.org/libreoffice/stable/${VER}/mac/x86_64/LibreOffice_${VER}_MacOS_x86-64.dmg"
    echo "下载 $url"; curl -fL "$url" -o "$tmp/lo.dmg"
    hdiutil attach "$tmp/lo.dmg" -mountpoint "$tmp/mnt" -nobrowse
    cp -R "$tmp/mnt/LibreOffice.app" "$DEST/"
    hdiutil detach "$tmp/mnt"
    xattr -dr com.apple.quarantine "$DEST/LibreOffice.app" || true
    ;;
  Linux)
    url="https://download.documentfoundation.org/libreoffice/stable/${VER}/deb/x86_64/LibreOffice_${VER}_Linux_x86-64_deb.tar.gz"
    echo "下载 $url"; curl -fL "$url" -o "$tmp/lo.tar.gz"
    tar -xzf "$tmp/lo.tar.gz" -C "$tmp"
    cp -R "$tmp"/LibreOffice_*/. "$DEST/"
    ;;
  *)
    echo "不支持的平台: $os —— 手动装 LibreOffice 并设 DOCANON_SOFFICE" >&2; exit 1;;
esac
echo "完成: $DEST"
echo "自检: ./scripts/dev.sh doctor"
```

`dev.sh::cmd_doctor` 在"引擎"段之前加：

```bash
  say "== 旧格式转换(LibreOffice) =="
  if command -v soffice >/dev/null 2>&1; then
    say "  $ok soffice            系统: $(command -v soffice)"
  elif [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    say "  $ok soffice            /Applications/LibreOffice.app"
  elif ls var/libreoffice/**/soffice >/dev/null 2>&1; then
    say "  $ok soffice            var/libreoffice"
  else
    say "  $no soffice            缺 —— .doc/.xls/.wps 将记 unsupported; 取: ./scripts/fetch_libreoffice.sh"
  fi
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_engines.py -q && bash -n scripts/fetch_libreoffice.sh`
Expected: PASS（脚本语法检查无输出）

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_libreoffice.sh scripts/dev.sh packages/docanon-core/src/docanon_core/inventory.py packages/docanon-core/tests/test_engines.py
git commit -m "feat: fetch_libreoffice 脚本 + doctor/engines 报 soffice 可用性"
```

---

### Task 8: 文档同步与决策记录

**Files:**
- Modify: `README.md`、`README.en.md`、`docs/quickstart.md`、`docs/quickstart.en.md`
- Modify: `docs/cookbook/diagnosing-problems.md:14`
- Modify: `.agent/rules/02-packages.md`、`03-resources.md`、`04-outputs.md`
- Modify: `CHANGELOG.md`、`AGENTS.md`（测试计数）
- Create: `.agent/notes/implemented/feature/2026-10-08-legacy-office-conversion.md`
- Modify: `.agent/rules/06-testing.md` 或 `docs/architecture.md`（链到新笔记）
- Test: `tests/test_docs.py`

**Interfaces:**
- Consumes: 前面所有任务。
- Produces: 文档与代码不漂移；新笔记被索引。

- [ ] **Step 1: 写决策笔记**

创建 `.agent/notes/implemented/feature/2026-10-08-legacy-office-conversion.md`：

```markdown
# Agent Note: 旧版 Office(.doc/.xls/.wps) 自动转换

Status: implemented

## 问题

旧格式一律 `unsupported`，且明知 LibreOffice 能转却**故意不自动转**（怕版式重排）。
用户侧代价：必须先手工转、且往往连 LibreOffice 都没装。

## 决定

在抽取层自动转换（系统优先 / 下载到 var/），并**显式标注**"产物已由 .doc 转换、版式可能重排"。
推翻了 cookbook 里的旧决定，理由：把语义变化写进账本与界面，比让用户手工前置更安全、更省事。
```

- [ ] **Step 2: 运行文档守卫，确认失败**

Run: `.venv/bin/python -m pytest tests/test_docs.py -q`
Expected: FAIL（README 输入列表/已知限制、笔记未索引、AGENTS 计数等）

- [ ] **Step 3: 同步文档**

- `README.md` 输入支持列表加 `.doc/.xls/.wps`（自动转换）；"已知限制"改为"转换后产物为 `.docx/.xlsx` 且版式可能被重排"。
- `docs/cookbook/diagnosing-problems.md:14` 改为：`npm run doctor` 看 soffice 是否可用；缺则 `./scripts/fetch_libreoffice.sh`；要关闭用 `legacy_convert: false`。
- `.agent/rules/02-packages.md` 提 `convert.py` 与 `LegacyOfficeExtractor`；`03-resources.md` 加 `libreoffice` 资源项；`04-outputs.md` 加账本字段 `source_suffix/output_format/converted`。
- `CHANGELOG.md` 记一条。
- 英文镜像：`README.en.md`、`docs/quickstart.en.md` 同步后跑
  `python3 website/scripts/sync-content.py --record-hashes`。
- 在 `docs/architecture.md` 的决策/链接处加一行指向新笔记（满足笔记必须被链到）。
- 改完若测试数变化，更新根 `AGENTS.md` 的「（N 项，约 M 秒）」。

- [ ] **Step 4: 全量校验**

Run: `./scripts/dev.sh test`
Expected: PASS（含 `test_docs.py`）

- [ ] **Step 5: Commit**

```bash
git add README.md README.en.md docs/ CHANGELOG.md AGENTS.md .agent/ website/content-manifest.json
git commit -m "docs: 旧格式自动转换的支持说明、限制、决策笔记"
```

---

## Self-Review

**Spec coverage:**
- §3 抽取层方案 A → T3/T4；`meta["out_ext"]` → T4；扩展名映射 → T3(`TARGETS`)/T4 测试。
- §4 soffice 定位 → T3；`LAYOUT` → T2；下载 → T7；doctor/engines → T7。
- §5 账本与标注 → T5；`SUPPORTED` → T5。
- §6 失败语义 → T4/T5 测试。
- §7 配置 → T6。
- §8 脚本/自检 → T7。
- §9 测试 → T3/T4/T5/T6/T7。
- §10 文档同步 → T1/T8。
- §11 风险：Gatekeeper(xattr) → T7 脚本；体积/重试 → T7（文档提示）；`.wps` 尽力 → T3/T4。

**Placeholder scan:** 无 TBD/TODO；所有代码步骤均给出实际代码。

**Type consistency:** `to_modern` 返回 `(Path, str)`；`find_soffice`/`unavailable_reason` 名称在 T3/T4/T5/T7 一致；`ProcessResult.converted_from`/`output_format` 在 T4 定义、T5 消费；账本键 `source_suffix`/`output_format`/`converted` 在 T5 写、T5/T6 断言。
