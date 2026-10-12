"""批量（选文件夹）的 HTTP 契约。

真服务的起停见 `conftest.py` 的 `ephemeral_server`（它的 `out_root` 指向 tmp_path，
所以"上传件落哪、产物落哪"都能直接断言）。

这一批的硬约束（对应 `.agent/rules/04-outputs.md` 与 05-security）：
- 批次保留相对子目录；任何来自浏览器的相对路径都要过 `_safe_join`。
- 每个文件走 `ok` / `unsupported` / `error` 三态 —— **不许静默少一份**。
- 映射表含原文，整包 zip 里不许带上它。
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from docanon_core import convert
from docanon_core.extractors.base import extractor_classes


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=120) as resp:
        return json.loads(resp.read())


def _post_status(base: str, path: str, payload: dict) -> int:
    """只关心状态码时用它（失败不该抛 HTTPError 打断断言）。"""
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _upload_batch(base: str, batch: str, files: dict[str, bytes]) -> None:
    for rel, raw in files.items():
        _post(base, "/api/upload", {
            "filename": rel.rsplit("/", 1)[-1], "relpath": rel, "batch": batch,
            "content_b64": base64.b64encode(raw).decode(),
        })


# ---------- 1. 扩展名清单 ----------


def test_formats_lists_registry_extensions(ephemeral_server):
    """清单只有一个出处: 抽取器注册表。加一个抽取器就该自动出现在这里。"""
    body = _get(ephemeral_server, "/api/formats")
    want = sorted({ext for cls in extractor_classes() for ext in cls.extensions})
    assert body["extensions"] == want
    assert ".docx" in body["extensions"] and ".pdf" in body["extensions"]


def test_cli_supported_matches_registry():
    """CLI 的 SUPPORTED 与注册表不许各自漂移（两份清单必须一致）。"""
    from docanon_core.cli import SUPPORTED

    legacy = set(convert.LEGACY_EXTENSIONS)
    registry = {ext for cls in extractor_classes() for ext in cls.extensions} - legacy
    assert SUPPORTED == registry


# ---------- 2. 批次上传 ----------


def test_upload_keeps_relative_dirs_within_batch(ephemeral_server, tmp_path):
    up = _post(ephemeral_server, "/api/upload", {
        "filename": "附件A.docx", "relpath": "合同/附件A.docx", "batch": "b1",
        "content_b64": base64.b64encode(b"x").decode(),
    })
    assert up["token"] == "b1"
    assert up["filename"] == "合同/附件A.docx"
    # 落盘保留层级, 而且能被 /uploads/ 取回（中文路径要过 unquote）
    assert (tmp_path / "uploads" / "b1" / "合同" / "附件A.docx").is_file()
    with urllib.request.urlopen(f"{ephemeral_server}{urllib.parse.quote(up['url'])}", timeout=5) as resp:
        assert resp.read() == b"x"


def test_upload_rejects_path_traversal(ephemeral_server, tmp_path):
    for rel in ("../evil.txt", "/etc/passwd", "a/../../evil.txt"):
        code = _post_status(ephemeral_server, "/api/upload", {
            "filename": "evil.txt", "relpath": rel, "batch": "b1",
            "content_b64": base64.b64encode(b"x").decode(),
        })
        assert code == 400, rel
    assert not (tmp_path.parent / "evil.txt").exists()


def test_upload_rejects_bad_batch_id(ephemeral_server):
    code = _post_status(ephemeral_server, "/api/upload", {
        "filename": "a.txt", "relpath": "a.txt", "batch": "../../etc",
        "content_b64": base64.b64encode(b"x").decode(),
    })
    assert code == 400


def test_upload_without_batch_is_unchanged(ephemeral_server, tmp_path):
    """单份上传的老行为逐字不动: 每份一个 token, 落 uploads/<token>/<文件名>。"""
    up = _post(ephemeral_server, "/api/upload", {
        "filename": "note.txt", "content_b64": base64.b64encode(b"hi").decode(),
    })
    assert up["token"] != "note.txt" and len(up["token"]) == 12
    assert (tmp_path / "uploads" / up["token"] / "note.txt").is_file()
    assert up["url"] == f"/uploads/{up['token']}/note.txt"


# ---------- 3. 进度 ----------


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


# ---------- 4. 批次跑 ----------


def test_batch_run_keeps_dirs_and_reports_every_file(ephemeral_server, tmp_path):
    _upload_batch(ephemeral_server, "b1", {
        "合同/note.txt": "张三 13812340000\n".encode(),
        "说明.md": "联系 李四 13998765432\n".encode(),
        "附件/无用.psd": b"\x00",   # 不支持的类型: 必须出现在结果里, 不许静默丢
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b1", "config": "default.yaml"})
    by_src = {r["source"]: r for r in body["results"]}
    assert by_src["合同/note.txt"]["status"] == "ok"
    assert by_src["说明.md"]["status"] == "ok"
    assert by_src["附件/无用.psd"]["status"] == "unsupported"
    assert by_src["附件/无用.psd"]["reason"]
    assert body["summary"] == {"total": 3, "ok": 2, "unsupported": 1, "error": 0}
    assert body["batch"] == {"cancelled": False, "total": 3}

    # 产物保留相对子目录, 且 URL 指得到
    rel_url = urllib.parse.quote(by_src["合同/note.txt"]["output_url"])
    with urllib.request.urlopen(f"{ephemeral_server}{rel_url}", timeout=10) as resp:
        assert resp.status == 200
    out_token = body["zip_url"].split("/api/batch/")[1].split("/")[0]
    assert (tmp_path / "outputs" / out_token / "合同" / "【脱敏版】note.txt").is_file()
    assert (tmp_path / "outputs" / out_token / "mapping.json").is_file()


def test_batch_ignores_hidden_files(ephemeral_server, tmp_path):
    """Mac 文件夹里必有的 .DS_Store 不许混进"不支持"; 隐藏项整层跳过。"""
    _upload_batch(ephemeral_server, "b2", {
        "note.txt": "张三 13812340000\n".encode(),
        ".DS_Store": b"junk",
        ".git/config": b"junk",
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b2", "config": "default.yaml"})
    assert [r["source"] for r in body["results"]] == ["note.txt"]


def test_batch_empty_or_missing_is_400(ephemeral_server, tmp_path):
    (tmp_path / "uploads" / "empty").mkdir(parents=True)
    for batch in ("empty", "nope", "../../etc"):
        code = _post_status(ephemeral_server, "/api/anonymize", {"batch": batch, "config": "default.yaml"})
        assert code == 400, batch


def test_batch_cancel_keeps_finished_work(ephemeral_server, tmp_path, monkeypatch):
    """取消（第 2 份抛 Cancelled）时: 第 1 份的产物与结果仍在, 账本也落盘 —— 不是"全部白跑"。"""
    from docanon_core.server import routes

    real = routes.process_file
    calls = {"n": 0}

    def fake(src, out_dir, cfg, store, rel=None, progress=None, cancel=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise routes.Cancelled()
        return real(src, out_dir, cfg, store, rel=rel, progress=progress, cancel=cancel)

    monkeypatch.setattr(routes, "process_file", fake)
    _upload_batch(ephemeral_server, "b4", {
        "a.txt": "张三 13812340000\n".encode(),
        "b.txt": "李四 13998765432\n".encode(),
        "c.txt": "王五 13700001111\n".encode(),
    })
    body = _post(ephemeral_server, "/api/anonymize", {"batch": "b4", "config": "default.yaml"})
    assert body["batch"] == {"cancelled": True, "total": 3}
    assert body["summary"] == {"total": 3, "ok": 1, "unsupported": 0, "error": 0}
    assert len(body["results"]) == 1
    out_token = body["zip_url"].split("/api/batch/")[1].split("/")[0]
    assert (tmp_path / "outputs" / out_token / "mapping.json").is_file()


def test_batch_too_many_files_is_400(ephemeral_server, tmp_path, monkeypatch):
    from docanon_core.server import routes

    monkeypatch.setattr(routes, "BATCH_MAX_FILES", 2)
    _upload_batch(ephemeral_server, "b5", {
        "a.txt": b"x", "b.txt": b"x", "c.txt": b"x",
    })
    code = _post_status(ephemeral_server, "/api/anonymize", {"batch": "b5", "config": "default.yaml"})
    assert code == 400


# ---------- 5. 整包下载 ----------


def test_batch_zip_has_outputs_but_not_mapping(ephemeral_server):
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
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert names, "空包"
        assert all("【脱敏版】" in n for n in names), names
        assert not any("mapping.json" in n for n in names), "映射表含原文, 不许进包"
        assert any(n.startswith("合同/") for n in names), names


def test_batch_zip_missing_out_dir_is_404(ephemeral_server):
    try:
        urllib.request.urlopen(f"{ephemeral_server}/api/batch/nope/zip", timeout=5)
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:  # pragma: no cover
        raise AssertionError("不存在的批次居然给了包")
