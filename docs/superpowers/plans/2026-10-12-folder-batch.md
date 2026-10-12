# 批量脱敏（选择文件夹）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 界面上能选一个文件夹，把里面所有可脱敏文档（含子目录）一次跑完，产物整包 zip 取走；每份标状态、可单独看前后对比，未处理的显示它的状态而不是空白对比。

**Architecture:** 后端在现有单份流程外面加一层批次循环 —— `pipeline.process_file(..., rel=…)` 本来就支持保留相对子目录，CLI 的 `_collect`（排序 + 跳过隐藏项）与三态归类是参照实现。前端把「列表」升级成带状态的行模型；批次是独立模式（列表显示批次的行，跑批走 `/api/anonymize{batch}`）。

**Tech Stack:** Python 3.12 标准库（`http.server` + `zipfile`）+ pytest；React 19 + Vite 6 + Tailwind 4；Playwright（WebKit）E2E。

**Spec:** [docs/specs/2026-10-12-folder-batch-design.md](../../docs/specs/2026-10-12-folder-batch-design.md)

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `packages/docanon-core/src/docanon_core/server/routes.py` | 新端点 + 批次编排（遍历、三态归类、打包） | 改 |
| `packages/docanon-core/src/docanon_core/server/progress.py` | 进度状态增加批次字段（file/index/total_files） | 改 |
| `packages/docanon-core/tests/test_server_batch.py` | formats / 批次上传 / 批次跑 / zip | 新建 |
| `apps/web/src/types.ts` | `DocRow` / `BatchFile` 模型 | 改 |
| `apps/web/src/lib/api.ts` | `loadFormats` / `uploadFile(+batch)` / `anonymizeBatch` | 改 |
| `apps/web/src/lib/formats.ts` | 进度文案带批次前缀；上限常量 | 改 |
| `apps/web/src/components/PresetList.tsx` | 行列表 + 状态徽标 + 文件夹入口 | 改 |
| `apps/web/src/components/StatsCard.tsx` | 批次汇总（三态计数） | 改 |
| `apps/web/src/App.tsx` | 文件夹流程、上传循环、跑批、下载、状态感知预览 | 改 |
| `apps/web/src/styles.css` | 状态徽标样式（复用现有 token，不加新色） | 改 |
| `.agent/rules/07-frontend.md` | 新增 DOM 钩子 | 改 |
| `CHANGELOG.md` | 记录 | 改 |

---

## Task 1: `/api/formats` —— 扩展名清单由抽取器注册表推导

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`
- Test: `packages/docanon-core/tests/test_server_batch.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""批量（选文件夹）的 HTTP 契约。真服务起停见 conftest.py 的 ephemeral_server。"""
from __future__ import annotations

import base64
import json
import urllib.request

from docanon_core import convert
from docanon_core.extractors.base import extractor_classes


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=60) as resp:
        return json.loads(resp.read())


def test_formats_lists_registry_extensions(ephemeral_server):
    """清单只有一个出处: 抽取器注册表。加一个抽取器就该自动出现在这里。"""
    body = _get(ephemeral_server, "/api/formats")
    want = sorted({ext for cls in extractor_classes() for ext in cls.extensions})
    assert body["extensions"] == want
    assert ".docx" in body["extensions"] and ".pdf" in body["extensions"]


def test_cli_supported_matches_registry():
    """CLI 的 SUPPORTED 与注册表不许各自漂移(两份清单必须一致)。"""
    from docanon_core.cli import SUPPORTED

    legacy = set(convert.LEGACY_EXTENSIONS)
    registry = {ext for cls in extractor_classes() for ext in cls.extensions} - legacy
    assert SUPPORTED == registry
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q`
Expected: FAIL（`/api/formats` 走静态兜底 → 404 → `HTTPError`）

- [ ] **Step 3: 实现**

`routes.py` 顶部（`_MAX_BYTES` 附近）加：

```python
def supported_extensions() -> list[str]:
    """界面上"选文件夹"预过滤用的扩展名清单。

    不另抄一份: 直接问抽取器注册表 —— 加个抽取器就自动出现在界面上。
    """
    from ..extractors.base import extractor_classes

    return sorted({ext for cls in extractor_classes() for ext in cls.extensions})
```

`do_GET` 里加一条分支（放在 `p == "/api/models"` 之前）：

```python
        elif p == "/api/formats":
            self._json(200, {"extensions": supported_extensions()})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add packages/docanon-core/tests/test_server_batch.py packages/docanon-core/src/docanon_core/server/routes.py
git commit -m "feat(server): /api/formats 扩展名清单由抽取器注册表推导"
```

---

## Task 2: 上传支持批次（`batch` + `relpath`，路径必须安全）

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`（`_upload`）
- Test: `packages/docanon-core/tests/test_server_batch.py`

- [ ] **Step 1: 写失败测试**

```python
def test_upload_keeps_relative_dirs_within_batch(ephemeral_server, tmp_path):
    up = _post(ephemeral_server, "/api/upload", {
        "filename": "附件A.docx", "relpath": "合同/附件A.docx", "batch": "b1",
        "content_b64": base64.b64encode(b"x").decode(),
    })
    assert up["token"] == "b1"
    assert up["filename"] == "合同/附件A.docx"
    # 落盘位置保留层级, 且能被 /uploads/ 取回(中文路径要过 unquote)
    assert (tmp_path / "uploads" / "b1" / "合同" / "附件A.docx").is_file()
    with urllib.request.urlopen(f"{ephemeral_server}{up['url']}", timeout=5) as resp:
        assert resp.read() == b"x"


def test_upload_rejects_path_traversal(ephemeral_server, tmp_path):
    import urllib.error

    for rel in ("../evil.txt", "/etc/passwd", "a/../../evil.txt"):
        req = urllib.request.Request(
            ephemeral_server + "/api/upload",
            data=json.dumps({
                "filename": "evil.txt", "relpath": rel, "batch": "b1",
                "content_b64": base64.b64encode(b"x").decode(),
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400, rel
        else:  # pragma: no cover
            raise AssertionError(f"{rel} 居然被放行了")
    assert not (tmp_path.parent / "evil.txt").exists()


def test_upload_without_batch_is_unchanged(ephemeral_server, tmp_path):
    """单份上传的老行为逐字不动: 每份一个 token, 落 uploads/<token>/<文件名>。"""
    up = _post(ephemeral_server, "/api/upload", {
        "filename": "note.txt", "content_b64": base64.b64encode(b"hi").decode(),
    })
    assert up["token"] != "note.txt" and len(up["token"]) == 12
    assert (tmp_path / "uploads" / up["token"] / "note.txt").is_file()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k upload`
Expected: 前两条 FAIL（`relpath`/`batch` 被忽略），第三条 passed

- [ ] **Step 3: 实现**

`_upload` 改为（保留原分支行为）：

```python
    def _upload(self, payload: dict) -> None:
        try:
            name = Path(payload["filename"]).name
            raw = base64.b64decode(payload["content_b64"])
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"上传失败: {exc}"})
            return
        if len(raw) > _MAX_BYTES:
            self._json(400, {"error": "文件过大(>50MB)"})
            return
        batch = payload.get("batch")
        if batch:
            # 批次: 一个文件夹里的多份进同一个目录, 保留相对层级
            if not progress.NAME_RE.match(str(batch)):
                self._json(400, {"error": "非法批次 id"})
                return
            rel = str(payload.get("relpath") or name).replace("\\", "/")
            dest = _safe_join(self.out_root / "uploads" / str(batch), rel)
            if dest is None:
                self._json(400, {"error": f"非法相对路径: {rel}"})
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            shown = rel
            token = str(batch)
        else:
            token = uuid.uuid4().hex[:12]
            dest = self.out_root / "uploads" / token / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            shown = name
        self._json(200, {"token": token, "filename": shown, "url": f"/uploads/{token}/{shown}"})
```

- [ ] **Step 4: 跑测试确认通过**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k upload`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add packages/docanon-core/tests/test_server_batch.py packages/docanon-core/src/docanon_core/server/routes.py
git commit -m "feat(server): 上传支持批次(保留相对目录, 拒绝路径穿越)"
```

---

## Task 3: 进度状态增加批次字段

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/progress.py`
- Test: `packages/docanon-core/tests/test_server_batch.py`

- [ ] **Step 1: 写失败测试**

```python
def test_progress_carries_batch_fields():
    """批次进度要能报"第 3/41 份 · 哪个文件"; 单份流程不传就保持空。"""
    from docanon_core.server import progress

    progress.clear()
    progress.begin("j1")
    assert progress.state("j1")["file"] == "" and progress.state("j1")["total_files"] == 0
    progress.update("j1", "detect", 3, 8, file="合同/附件A.docx", index=3, total_files=41)
    st = progress.state("j1")
    assert (st["stage"], st["done"], st["total"]) == ("detect", 3, 8)
    assert (st["file"], st["index"], st["total_files"]) == ("合同/附件A.docx", 3, 41)
    # 单份那种"只传 stage/done/total"的调用不许把批次字段擦掉
    progress.update("j1", "write", 1, 1)
    st = progress.state("j1")
    assert (st["file"], st["index"], st["total_files"]) == ("合同/附件A.docx", 3, 41)
    progress.clear()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k progress`
Expected: FAIL（`KeyError: 'file'`）

- [ ] **Step 3: 实现**

`begin` 的初始字典补三个键：

```python
        _jobs[job_id] = {
            "stage": "extract", "done": 0, "total": 0, "cancelled": False, "cancel": cancel,
            "file": "", "index": 0, "total_files": 0,
        }
```

`update` 改成"传了才改"（否则单份流程的 `progress(stage, done, total)` 会把批次信息擦掉）：

```python
def update(
    job_id: str, stage: str, done: int = 0, total: int = 0,
    *, file: str | None = None, index: int | None = None, total_files: int | None = None,
) -> None:
    """更新进度。批次字段是可选的: 传了才覆盖 —— 单份流程不传, 不会把它擦掉。"""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(stage=stage, done=done, total=total)
        if file is not None:
            job["file"] = file
        if index is not None:
            job["index"] = index
        if total_files is not None:
            job["total_files"] = total_files
```

`state` 的返回补三个键（未知任务也补，前端不用分支）：

```python
        return {
            "stage": job["stage"], "done": job["done"], "total": job["total"],
            "cancelled": job["cancelled"],
            "file": job.get("file", ""), "index": job.get("index", 0),
            "total_files": job.get("total_files", 0),
        }
```
（`job is None` 的分支同样补 `"file": "", "index": 0, "total_files": 0`。）

- [ ] **Step 4: 跑测试确认通过**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k progress`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add packages/docanon-core/tests/test_server_batch.py packages/docanon-core/src/docanon_core/server/progress.py
git commit -m "feat(server): 进度状态增加批次字段(file/index/total_files)"
```

---

## Task 4: `/api/anonymize{batch}` —— 一批跑完，逐份三态

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`
- Test: `packages/docanon-core/tests/test_server_batch.py`

- [ ] **Step 1: 写失败测试**

```python
def _upload_batch(base: str, batch: str, files: dict[str, bytes]) -> None:
    for rel, raw in files.items():
        _post(base, "/api/upload", {
            "filename": rel.rsplit("/", 1)[-1], "relpath": rel, "batch": batch,
            "content_b64": base64.b64encode(raw).decode(),
        })


def test_batch_run_keeps_dirs_and_reports_every_file(ephemeral_server, tmp_path):
    _upload_batch(ephemeral_server, "b1", {
        "合同/note.txt": "张三 13812340000\n".encode(),
        "说明.md": "联系 李四 13998765432\n".encode(),
        "附件/图.psd": b"\x00",            # 不支持的类型: 必须出现在结果里, 不许静默丢
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b1", "config": "default.yaml"})
    by_src = {r["source"]: r for r in body["results"]}
    assert by_src["合同/note.txt"]["status"] == "ok"
    assert by_src["说明.md"]["status"] == "ok"
    assert by_src["附件/图.psd"]["status"] == "unsupported"
    assert by_src["附件/图.psd"]["reason"]
    assert body["summary"] == {"total": 3, "ok": 2, "unsupported": 1, "error": 0}
    # 产物保留相对子目录
    out = tmp_path / "outputs"
    hits = sorted(p.relative_to(out).parts[1:2] and "/".join(p.relative_to(out).parts[1:3]) for p in out.rglob("*.txt"))
    assert any(h.startswith("合同/") for h in hits), hits
    assert body["mapping_url"].endswith("/mapping.json")
    assert body["zip_url"].startswith("/api/batch/")
    assert (out / body["zip_url"].split("/api/batch/")[1].split("/")[0] / "mapping.json").is_file()


def test_batch_ignores_hidden_files(ephemeral_server, tmp_path):
    _upload_batch(ephemeral_server, "b2", {
        "note.txt": "张三 13812340000\n".encode(),
        ".DS_Store": b"junk",
        ".git/config": b"junk",
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b2", "config": "default.yaml"})
    assert [r["source"] for r in body["results"]] == ["note.txt"]


def test_batch_empty_or_missing_is_400(ephemeral_server, tmp_path):
    import urllib.error

    (tmp_path / "uploads" / "empty").mkdir(parents=True)
    for batch in ("empty", "nope"):
        req = urllib.request.Request(
            ephemeral_server + "/api/anonymize",
            data=json.dumps({"batch": batch, "config": "default.yaml"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400, batch
        else:  # pragma: no cover
            raise AssertionError(f"{batch} 居然被受理了")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k batch`
Expected: FAIL（`batch` 未处理 → 400 缺 preset/token）

- [ ] **Step 3: 实现**

`routes.py` 模块级加两个常量与一个遍历函数（规则与 CLI 的 `_collect` 一致）：

```python
BATCH_MAX_FILES = 300
BATCH_MAX_BYTES = 500 * 1024 * 1024


def _batch_files(root: Path) -> list[tuple[Path, Path]]:
    """批次目录里的 (绝对路径, 相对路径), 按相对路径排序。

    跳过隐藏项(`.` 开头, 含任何一层) —— 与 CLI `_collect` 同一套规则: 否则每个 Mac 文件夹
    都会多出一堆 `.DS_Store` 进"不支持"。隐藏项不算 unsupported, 由调用方单独报"已忽略 N 个"。
    """
    return [
        (p, p.relative_to(root))
        for p in sorted(root.rglob("*"))
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)
    ]
```

`_anonymize_job` 里，在 `# 输入来源` 之前插一条批次分支：

```python
        if payload.get("batch"):
            self._anonymize_batch(str(payload["batch"]), cfg, payload, job, cancel)
            return
```

新增方法 `_anonymize_batch`：

```python
    def _anonymize_batch(self, batch: str, cfg, payload: dict, job: str | None, cancel) -> None:
        """一批跑完。每份是独立的原子单位: 完成的那些即使后面取消/失败也已经落盘。

        三态与 CLI 一致: 不支持的记 unsupported(带原因), 出错的记 error, 绝不**静默少一份**。
        """
        if not progress.NAME_RE.match(batch):
            self._json(400, {"error": "非法批次 id"})
            return
        src_root = self.out_root / "uploads" / batch
        pairs = _batch_files(src_root) if src_root.is_dir() else []
        if not pairs:
            self._json(400, {"error": "这个文件夹里没有可脱敏的文档"})
            return
        if len(pairs) > BATCH_MAX_FILES:
            self._json(400, {"error": f"一次最多 {BATCH_MAX_FILES} 份(当前 {len(pairs)} 份), 分两批跑"})
            return
        total_bytes = sum(p.stat().st_size for p, _ in pairs)
        if total_bytes > BATCH_MAX_BYTES:
            self._json(400, {"error": "整批超过 500MB, 分两批跑"})
            return

        legacy_blocked = None
        if any(p.suffix.lower() in convert.LEGACY_EXTENSIONS for p, _ in pairs):
            legacy_blocked = convert.unavailable_reason()

        token = uuid.uuid4().hex[:12]
        work = self.out_root / "outputs" / token
        work.mkdir(parents=True, exist_ok=True)
        store = MappingStore()
        results: list[dict] = []
        cancelled = False
        total = len(pairs)

        def tick(stage: str, done: int = 0, tot: int = 0, rel: str = "", i: int = 0) -> None:
            if job is not None:
                progress.update(job, stage, done, tot, file=rel, index=i, total_files=total)

        for i, (src, rel) in enumerate(pairs, start=1):
            rel_s = str(rel)
            tick("extract", 0, 0, rel_s, i)
            if legacy_blocked and src.suffix.lower() in convert.LEGACY_EXTENSIONS:
                results.append({"source": rel_s, "status": "unsupported", "reason": legacy_blocked})
                continue
            try:
                res = process_file(src, work, cfg, store, rel=rel, progress=(
                    None if job is None else (lambda stage, done=0, tot=0, _s=rel_s, _i=i: tick(stage, done, tot, _s, _i))
                ), cancel=cancel)
            except Cancelled:
                cancelled = True
                break
            except ValueError as exc:      # build_extractor: 不支持的类型
                results.append({"source": rel_s, "status": "unsupported", "reason": str(exc)})
                continue
            except Exception as exc:  # noqa: BLE001
                results.append({"source": rel_s, "status": "error", "reason": str(exc)})
                continue
            out_name = Path(res.output_path).name
            out_rel = str(res.output_path.relative_to(work)).replace(os.sep, "/")
            results.append({
                "source": rel_s, "status": "ok", "output_name": out_name,
                "output_url": f"/outputs/{token}/{out_rel}",
                "counts": res.entity_counts,
            })
        store.save(work / "mapping.json")   # 取消也要落账本: 已完成的部分不能白跑

        summary = {
            "total": total,
            "ok": sum(1 for r in results if r["status"] == "ok"),
            "unsupported": sum(1 for r in results if r["status"] == "unsupported"),
            "error": sum(1 for r in results if r["status"] == "error"),
        }
        self._json(200, {
            "batch": {"cancelled": cancelled},
            "summary": summary,
            "results": results,
            "mapping_url": f"/outputs/{token}/mapping.json",
            "zip_url": f"/api/batch/{token}/zip",
        })
```

注意：`payload["name"]`（文件夹名）不用传给后端 —— zip 的下载名由前端在 URL 上带（见 Task 5）。

- [ ] **Step 4: 跑测试确认通过**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k batch`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add packages/docanon-core/tests/test_server_batch.py packages/docanon-core/src/docanon_core/server/routes.py
git commit -m "feat(server): /api/anonymize 支持批次(保留目录, 逐份三态, 取消留已完成)"
```

---

## Task 5: `/api/batch/<out>/zip` —— 整包取走（不含映射表）

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`
- Test: `packages/docanon-core/tests/test_server_batch.py`

- [ ] **Step 1: 写失败测试**

```python
def test_batch_zip_has_outputs_but_not_mapping(ephemeral_server, tmp_path):
    _upload_batch(ephemeral_server, "b3", {
        "合同/note.txt": "张三 13812340000\n".encode(),
        "说明.md": "李四 13998765432\n".encode(),
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b3", "config": "default.yaml"})
    url = body["zip_url"] + "?name=" + urllib.parse.quote("我的案子")
    with urllib.request.urlopen(ephemeral_server + url, timeout=30) as resp:
        assert resp.headers["Content-Type"] == "application/zip"
        # 中文名要按 RFC 5987 编码, 否则浏览器存成 "download.zip"
        assert "filename*=UTF-8''" in resp.headers["Content-Disposition"]
        raw = resp.read()
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert all("【脱敏版】" in n for n in names), names
        assert not any("mapping.json" in n for n in names), "映射表含原文, 不许进包"
        assert any(n.startswith("合同/") for n in names), names
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k zip`
Expected: FAIL（404，静态兜底）

- [ ] **Step 3: 实现**

`routes.py` 模块级加：

```python
def _make_zip(out_dir: Path, dest: Path) -> int:
    """把 out_dir 下的产物打成一个 zip, **不含 mapping.json**(它含原文, 是与脱敏件分开外发的)。"""
    import zipfile

    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out_dir.rglob("*")):
            if path.is_file() and path.name != "mapping.json":
                zf.write(path, path.relative_to(out_dir))
                count += 1
    return count
```

Handler 加下载方法（流式，整包可能几百 MB，不能 `read_bytes`）：

```python
    def _send_download(self, path: Path, filename: str) -> None:
        """带 Content-Disposition 的下载。文件名按 RFC 5987 编码(中文名不许乱码)。"""
        if not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        self.send_response(200)
        self.send_header("Content-Type", _ctype(path))
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
        self.end_headers()
        with path.open("rb") as fh:
            shutil.copyfileobj(fh, self.wfile, 1 << 16)
```

（`_ctype` 对 `.zip` 要给出 `application/zip`；若不是，则在 `_ctype` 里补一条。）

`do_GET` 里加一条分支（放在 `/uploads/` `/outputs/` 静态分支**之前**）：

```python
        elif p.startswith("/api/batch/"):
            self._get_batch_zip(p[len("/api/batch/"):], query)
```

其中 `query` 取 `self.path.split("?", 1)[1]` 的 `name`（`unquote` 后 `Path(...).name` 兜底为"脱敏产物"）。实现：

```python
    def _get_batch_zip(self, rest: str, query: str) -> None:
        out = _safe_join(self.out_root / "outputs", rest.split("/", 1)[0])
        if out is None or not out.is_dir():
            self._json(404, {"error": "批次产物不存在"})
            return
        name = "脱敏产物"
        for part in query.split("&"):
            if part.startswith("name="):
                name = Path(unquote(part[len("name="):])).name or name
        tmp = self.out_root / f"zip-{uuid.uuid4().hex[:8]}.zip"
        try:
            _make_zip(out, tmp)
            self._send_download(tmp, f"【脱敏版】{name}.zip")
        finally:
            tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `./scripts/dev.sh test packages/docanon-core/tests/test_server_batch.py -q -k zip`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add packages/docanon-core/tests/test_server_batch.py packages/docanon-core/src/docanon_core/server/routes.py
git commit -m "feat(server): /api/batch/<out>/zip 整包下载(不含映射表)"
```

---

## Task 6: 前端数据模型与 API 客户端

**Files:**
- Modify: `apps/web/src/types.ts`, `apps/web/src/lib/api.ts`

- [ ] **Step 1: 加类型**

```ts
/** 列表里每一行的状态: 批次下"已处理好的看对比, 没处理好的显示状态"就靠它 */
export type DocStatus = "idle" | "running" | "ok" | "unsupported" | "error";

export type DocRow = {
  key: string;
  /** 显示名(批次里是相对路径) */
  name: string;
  /** 右侧来源标签: TXT / 已上传 / 文件夹 */
  tag: string;
  status: DocStatus;
  counts?: Record<string, number>;
  outputName?: string;
  outputUrl?: string;
  reason?: string;
  /** 选中它用的东西(与 Selection 同形) */
  ref: { preset: string } | { token: string; filename: string; url: string };
};

export type BatchFileResult = {
  source: string;
  status: "ok" | "unsupported" | "error";
  output_name?: string;
  output_url?: string;
  counts?: Record<string, number>;
  reason?: string;
};

/** 一批跑完的响应(与 GET /api/anonymize{batch} 同形) */
export type AnonymizeBatchResp = {
  batch: { cancelled: boolean };
  summary: { total: number; ok: number; unsupported: number; error: number };
  results: BatchFileResult[];
  mapping_url: string;
  zip_url: string;
};
```

`ProgressState` 增加：

```ts
  /** 批次进度: 第几份 / 共几份 / 哪一份(单份流程都是空) */
  file?: string;
  index?: number;
  total_files?: number;
```

- [ ] **Step 2: 加 API**

```ts
export const loadFormats = () => plainJson<{ extensions: string[] }>("/api/formats");

/** 上传一份文件。带 batch 时落进批次目录并保留 relpath(选文件夹用)。 */
export const uploadFile = (file: File, batch?: { id: string; relpath: string }) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.onload = () => {
      const b64 = String(reader.result).split(",", 2)[1] ?? "";
      postJson<UploadResp>("/api/upload", {
        filename: file.name,
        content_b64: b64,
        ...(batch ? { batch: batch.id, relpath: batch.relpath } : {}),
      }).then(() => resolve(b64)).catch(reject);
    };
    reader.readAsDataURL(file);
  });

export const anonymizeBatch = (payload: { batch: string; config?: string | ConfigData; job?: string }) =>
  postJson<AnonymizeBatchResp>("/api/anonymize", payload);
```

（现有 `uploadFile` 的实现就地改签名，保留"读成 base64 → POST"的形状；调用方在 Task 8 同步改。）

- [ ] **Step 3: 类型自检**

Run: `npm run build:web`
Expected: 通过（此时调用方还没改，若报 `uploadFile` 参数不符，说明签名已生效，继续 Task 8 即可）

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/types.ts apps/web/src/lib/api.ts
git commit -m "feat(web): 批次相关的类型与 API 客户端"
```

---

## Task 7: 列表行渲染（状态徽标）+ 批次汇总

**Files:**
- Modify: `apps/web/src/components/PresetList.tsx`, `apps/web/src/components/StatsCard.tsx`, `apps/web/src/styles.css`

- [ ] **Step 1: 行渲染改造**

`PresetList` 的入参从 `presets/uploads/activeName` 换成 `rows: DocRow[]` + `activeKey: string | null`，
渲染 `.doc-row`（示例行**同时保留 `.preset` 类**，E2E 契约不许改）：

```tsx
const STATUS: Record<DocStatus, { text: string; cls: string }> = {
  idle: { text: "待跑", cls: "text-muted-foreground" },
  running: { text: "跑中", cls: "text-foreground" },
  ok: { text: "✓", cls: "text-selected" },
  unsupported: { text: "未处理", cls: "text-muted-foreground" },
  error: { text: "失败", cls: "text-destructive" },
};

// 一行 = 来源标签 + 状态徽标; 已脱敏的把那一下"抹了多少处"也带上, 一眼能看出哪份处理好了
<button
  key={row.key}
  type="button"
  aria-pressed={active}
  className={`${row.kind === "preset" ? "preset " : ""}doc-row mb-1.5 flex w-full …`}
  title={row.reason ? `${row.name} —— ${row.reason}` : row.name}
  onClick={() => onPick(row)}
>
  <span aria-hidden>📄</span>
  <span className="min-w-0 flex-1 truncate">{row.name}</span>
  {row.status === "ok" && row.counts ? (
    <span className="flex-none text-[11px] tabular-nums text-muted-foreground">✓ {totalCounts(row.counts)} 处</span>
  ) : (
    <span className={`flex-none text-[11px] ${STATUS[row.status].cls}`} title={row.reason ?? ""}>
      {STATUS[row.status].text}
    </span>
  )}
</button>
```

- [ ] **Step 2: 批次汇总**

`StatsCard` 增加可选 `summary` 入参，在标题行右侧补三态计数（`#stats` 位置不动）：

```tsx
{summary ? (
  <span className="text-xs text-muted-foreground">
    {summary.total} 份：{summary.ok} 已脱敏
    {summary.unsupported ? ` · ${summary.unsupported} 未处理` : ""}
    {summary.error ? ` · ${summary.error} 失败` : ""}
  </span>
) : null}
```

`styles.css` 只加状态徽标用的过渡与字重（**不引入新色**，颜色全部走 `text-muted-foreground` /
`text-selected` / `text-destructive`）。

- [ ] **Step 3: 构建自检**

Run: `npm run build:web`
Expected: `tsc --noEmit` 通过

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/components apps/web/src/styles.css
git commit -m "feat(web): 文档行带状态徽标 + 批次汇总"
```

---

## Task 8: App —— 文件夹入口、上传循环、跑批、下载、状态感知预览

**Files:**
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: 状态模型**

```tsx
const [rows, setRows] = useState<DocRow[]>([]);          // 列表(示例/单份/批次共用)
const [batch, setBatch] = useState<{ id: string; folder: string; zipUrl: string; mappingUrl: string } | null>(null);
const [formats, setFormats] = useState<string[]>([]);     // /api/formats, 选文件夹时预过滤
const [uploading, setUploading] = useState(false);
const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
const [progress, setProgress] = useState<ProgressState | null>(null);
```

- [ ] **Step 2: 选文件夹**

```tsx
const FOLDER_MAX_FILES = 300;
const FOLDER_MAX_BYTES = 500 * 1024 * 1024;

const pickFolder = async (fileList: File[]) => {
  // webkitRelativePath 形如 "合同材料/合同/附件A.docx" —— 第一段是文件夹名, 去掉它才是批次内的相对路径
  const picked = fileList.map((f) => ({
    file: f,
    relpath: (f.webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name,
  })).filter((x) => !x.relpath.split("/").some((p) => p.startsWith(".")));
  const folder = (fileList[0]?.webkitRelativePath || "").split("/")[0] || "文件夹";
  const ok = picked.filter((x) => formats.includes(extOf(x.file.name)));
  const bad = picked.filter((x) => !formats.includes(extOf(x.file.name)));
  const tooBig = ok.filter((x) => x.file.size > 50 * 1024 * 1024);
  const todo = ok.filter((x) => x.file.size <= 50 * 1024 * 1024);
  const totalBytes = todo.reduce((n, x) => n + x.file.size, 0);
  if (!todo.length) { setError("这个文件夹里没有可脱敏的文档"); return; }
  if (todo.length > FOLDER_MAX_FILES || totalBytes > FOLDER_MAX_BYTES) {
    setError(`一次最多 ${FOLDER_MAX_FILES} 份 / 500MB（这次 ${todo.length} 份），分两批跑`);
    return;
  }
  const id = `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  // 不支持与超限的也进列表(唯一去处), 状态就写未处理 + 原因
  setRows([
    ...todo.map((x) => ({ key: `${id}:${x.relpath}`, name: x.relpath, tag: "文件夹",
                          status: "idle" as const, ref: { token: id, filename: x.relpath, url: `/uploads/${id}/${x.relpath}` } })),
    ...bad.map((x) => ({ key: `${id}:${x.relpath}`, name: x.relpath, tag: "文件夹",
                         status: "unsupported" as const, reason: `${extOf(x.file.name) || "无扩展名"} 不支持`,
                         ref: { token: id, filename: x.relpath, url: "" } })),
    ...tooBig.map((x) => ({ key: `${id}:${x.relpath}`, name: x.relpath, tag: "文件夹",
                            status: "unsupported" as const, reason: "超过 50MB 上限",
                            ref: { token: id, filename: x.relpath, url: "" } })),
  ]);
  setBatch({ id, folder, zipUrl: "", mappingUrl: "" });
  setSelection(null);
  setResult(null);
  setUploading(true);
  setUploadProgress({ done: 0, total: todo.length });
  const failed: { relpath: string; reason: string }[] = [];
  for (const [i, x] of todo.entries()) {
    try {
      await api.uploadFile(x.file, { id, relpath: x.relpath });
    } catch (e) {
      failed.push({ relpath: x.relpath, reason: (e as Error).message });
    }
    setUploadProgress({ done: i + 1, total: todo.length });
  }
  setUploading(false);
  setUploadProgress(null);
  if (failed.length) {
    const bad = new Set(failed.map((f) => f.relpath));
    const why = new Map(failed.map((f) => [f.relpath, f.reason]));
    setRows((prev) => prev.map((r) => bad.has(r.name) ? { ...r, status: "error", reason: `上传失败：${why.get(r.name)}` } : r));
  }
};
```

- [ ] **Step 3: 跑批**

```tsx
const runBatch = async () => {
  if (!batch) return;
  setRunning(true); setError(null); setProgress(null); setStartedAt(Date.now());
  const job = `job-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  runningJob.current = job;
  const poll = window.setInterval(() => { api.runProgress(job).then(setProgress).catch(() => {}); }, 600);
  setRows((prev) => prev.map((r) => r.status === "idle" ? { ...r, status: "running" } : r));
  try {
    const resp = await api.anonymizeBatch({ batch: batch.id, job, ...(configPayload()) });
    const bySource = new Map(resp.results.map((r) => [r.source, r]));
    setRows((prev) => prev.map((r) => {
      const hit = bySource.get(r.name);
      if (!hit) return r;
      return hit.status === "ok"
        ? { ...r, status: "ok", counts: hit.counts, outputName: hit.output_name, outputUrl: hit.output_url, reason: undefined }
        : { ...r, status: hit.status, reason: hit.reason };
    }));
    setBatch((b) => (b ? { ...b, zipUrl: resp.zip_url, mappingUrl: resp.mapping_url } : b));
    setBatchSummary(resp.summary);
    if (resp.batch.cancelled) setNotice(`已取消 · 已跑完 ${resp.summary.ok + resp.summary.unsupported + resp.summary.error}/${resp.summary.total}`);
  } catch (e) {
    const msg = (e as Error).message;
    setRows((prev) => prev.map((r) => r.status === "running" ? { ...r, status: "idle" } : r));
    setError(msg.includes("已取消") ? null : `脱敏失败: ${msg}`);
  } finally {
    window.clearInterval(poll); setProgress(null); setStartedAt(null); runningJob.current = null; setRunning(false);
  }
};
```

- [ ] **Step 4: 状态感知预览（用户明确要的那条）**

```tsx
const pickRow = (row: DocRow) => {
  setSelection({ preset: "preset" in row.ref ? row.ref.preset : null,
                 token: "token" in row.ref ? row.ref.token : null,
                 filename: row.name,
                 url: "url" in row.ref ? row.ref.url : "" });
  // 已处理好的 → 右栏给对比; 没处理好的 → 右栏显示它的状态(N 处/未处理原因/失败原因/待跑)
  setResult(row.status === "ok" && row.outputUrl
    ? { output_name: row.outputName ?? "", output_url: row.outputUrl, counts: row.counts ?? {}, kind: "" }
    : null);
  setResultPlaceholder(outStateText(row, progress));
  setDrawerOpen(false);
};
```

`Preview` 的 `placeholder` 传 `outStateText(...)`（组件不用改）：

```tsx
const outStateText = (row: DocRow | null, p: ProgressState | null): string => {
  if (!row) return "点击「一键脱敏」查看结果";
  switch (row.status) {
    case "ok": return "正在加载脱敏件…";
    case "running": return `正在处理：${progressInfo(p).label}`;
    case "unsupported": return `未处理：${row.reason ?? "该类型暂不支持"}`;
    case "error": return `失败：${row.reason ?? "未知原因"}`;
    default: return "还没跑 —— 点「一键脱敏」";
  }
};
```

- [ ] **Step 5: 入口与下载按钮**

```tsx
{/* webkitdirectory 在 WKWebView 里未必放行: 先探测, 没有这个属性就不显示入口(不装作能用) */}
{hasFolderPicker ? (
  <>
    <input ref={folderRef} type="file" hidden multiple
           {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
           onChange={(e) => { void pickFolder([...(e.target.files ?? [])]); e.target.value = ""; }} />
    <Button id="pickFolder" className="w-full flex-none" disabled={uploading} onClick={() => folderRef.current?.click()}>
      {uploading ? `上传中 ${uploadProgress?.done ?? 0}/${uploadProgress?.total ?? 0}` : "选择文件夹…"}
    </Button>
  </>
) : null}
…
{batch?.zipUrl ? (
  <a id="downloadZip" href={batch.zipUrl + `?name=${encodeURIComponent(batch.folder)}`} download
     className="…">打包下载（zip）</a>
) : null}
```

`hasFolderPicker` 在模块级算一次：`"webkitdirectory" in HTMLInputElement.prototype`。

- [ ] **Step 6: 构建 + 真跑**

Run: `npm run build:web`
Run: `npm run dev`（另开终端）→ 用 `samples/` 当"文件夹"选一次，确认列表出现状态徽标、跑完显示 ✓ N 处、点行能看到前后对比、zip 能下载

- [ ] **Step 7: 提交**

```bash
git add apps/web/src/App.tsx apps/web/src/lib/formats.ts
git commit -m "feat(web): 选择文件夹一批跑完(状态徽标/前后对比/整包下载)"
```

---

## Task 9: 进度文案带批次前缀

**Files:**
- Modify: `apps/web/src/lib/formats.ts`

- [ ] **Step 1: 改 `progressInfo`**

```ts
export function progressInfo(
  state: { stage: string; done: number; total: number; file?: string; index?: number; total_files?: number } | null,
): { label: string; pct: number | null } {
  if (!state) return { label: "正在开始…", pct: null };
  const base = STAGE_LABELS[state.stage] ?? "处理中";
  const detail = state.stage === "detect" && state.total
    ? `${base} ${state.done}/${state.total} 段`
    : `${base}…`;
  // 批次: 前面补"第 i/N 份 · 哪个文件", 否则一排文件跑起来不知道现在到哪儿了
  const prefix = state.total_files ? `第 ${state.index}/${state.total_files} 份 · ` : "";
  return { label: prefix + detail, pct: state.stage === "detect" && state.total ? Math.round((state.done / state.total) * 100) : null };
}
```

- [ ] **Step 2: 构建自检**

Run: `npm run build:web` → Expected: 通过

- [ ] **Step 3: 提交**

```bash
git add apps/web/src/lib/formats.ts
git commit -m "feat(web): 进度文案带批次前缀(第 i/N 份 · 文件名)"
```

---

## Task 10: 规则、CHANGELOG 与 E2E

**Files:**
- Modify: `.agent/rules/07-frontend.md`, `CHANGELOG.md`, `tests/e2e/webkit/webkit-check.mjs`

- [ ] **Step 1: 登记 DOM 契约**

`07-frontend.md` 的 DOM 契约那一条补：`#pickFolder`、`.doc-row`、`#downloadZip`、`#batchSummary`
（`.preset` 仍在示例行上，`#stats` 位置不变）。

- [ ] **Step 2: CHANGELOG**

`[Unreleased] → Added` 记：能选文件夹一批跑完；每份标状态（已脱敏 N 处 / 未处理原因 / 失败）；
点已处理的可看前后对比、未处理的显示其状态；整包 zip 下载（不含映射表）。

- [ ] **Step 3: E2E 加一条文件夹路径**

`webkit-check.mjs` 末尾加（用 `samples/` 当文件夹：`setInputFiles` 传多文件时会带 `webkitRelativePath`）：

```js
// 选文件夹: 一批跑完 → 每行有状态 → 点已处理的能看对比
await page.locator('#pickFolder').click();
const input = page.locator('input[webkitdirectory]');
await input.setInputFiles(['samples/sample.docx', 'samples/sample.csv', 'samples/note.md']);
await page.waitForSelector('.doc-row', { timeout: 15000 });
await page.locator('#run').click();
await page.waitForSelector('.doc-row[data-status="ok"]', { timeout: 120000 });
const summary = await page.locator('#batchSummary').innerText();
console.log('[folder] 批次汇总:', summary.replace(/\s+/g, ' ').trim());
await page.locator('.doc-row').first().click();
await wait(1500);
console.log('[folder] 点行后 #paneOut 可见:', await page.locator('#paneOut').isVisible());
```

- [ ] **Step 4: 真跑一次 E2E**

Run: `DOCANON_URL=http://127.0.0.1:5173 node webkit-check.mjs`（在 `tests/e2e/webkit/` 下）
Expected: 输出 `[folder] …` 两行且零 console 错误

- [ ] **Step 5: 提交**

```bash
git add .agent/rules/07-frontend.md CHANGELOG.md tests/e2e/webkit/webkit-check.mjs
git commit -m "docs+test(web): 登记批次 DOM 钩子、CHANGELOG 与 E2E 文件夹路径"
```

---

## Task 11: 桌面壳验证 `webkitdirectory`（必须人点一次）

**Files:** 无代码改动（未通过时的兜底见 spec）

- [ ] **Step 1: 起壳**

Run: `./scripts/dev.sh desktop`

- [ ] **Step 2: 点「选择文件夹…」**

Expected: 弹出系统目录选择框；选一个文件夹后列表出现带状态的行。
未弹出（按钮不显示也算未通过）→ 按 spec 的兜底加 `tauri-plugin-dialog`，取其路径后仍走同一条上传链路。

- [ ] **Step 3: 把结果写进 spec 的"风险"一节**

改 `docs/specs/2026-10-12-folder-batch-design.md`：把"先验证的一条"改成实测结论（通过 / 已加插件）。

- [ ] **Step 4: 提交**

```bash
git add docs/specs/2026-10-12-folder-batch-design.md
git commit -m "docs(specs): 记 webkitdirectory 在 WKWebView 的实测结论"
```

---

## 自查

- **Spec 覆盖**：`/api/formats` → T1；批次上传 + 路径安全 → T2；进度 → T3；批次跑 + 三态 + 取消 → T4；
  zip（不含映射表）→ T5；预过滤与上限 → T8 Step 2；列表状态徽标 → T7；批次汇总 → T7；
  状态感知预览（用户新要求：已处理看对比、未处理显示状态）→ T8 Step 4；隐藏项跳过 → T4 Step 3；
  DOM 契约与 CHANGELOG → T10；WKWebView 风险 → T11。无遗漏。
- **占位符**：无 TBD/TODO；每个代码步骤都给了可直接落地的实现。
- **类型一致**：`DocRow.status` 与后端 `status` 三态一致（`idle/running` 是纯前端态）；
  `zip_url`/`mapping_url` 在 T4 产出、T8 消费；`progress.update` 的 `file/index/total_files`
  在 T3 定义、T4 传、T9 显示。
