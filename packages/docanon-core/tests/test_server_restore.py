"""`/api/restore` 的对外契约。

这个端点接受外部输入, 所以守的是三件事:

1. **路径不可穿越** —— `token` 只认服务端自己发过的那一串; 文件名只取 basename。
   否则就是"任意读服务端文件 + 任意写"。
2. **产物要能下载、报告要能对账** —— 界面拿不到还原件就等于没做。
3. **漏了/多了都要说** —— `complete=false` 时界面必须能区分这两种情况,
   因为处理方式相反: missing 要人工核对, unknown 是 AI 编的、别去替换。
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
import zipfile
from urllib.parse import quote

import pytest


@pytest.fixture
def base(ephemeral_server):
    """服务地址。沿用 conftest 的 `ephemeral_server`(out_root 指向 tmp_path, 不碰真实 var/)。"""
    return ephemeral_server


def _post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_status": exc.code, **json.loads(exc.read())}


def _fetch(base: str, url: str) -> bytes:
    # 产物名带中文(【脱敏版】), 浏览器会自动 percent-encode, 这里得手动做 —— 这也正是
    # 后端 `_path()` 必须 unquote 的原因(见 routes.py)
    quoted = quote(url, safe="/%")
    with urllib.request.urlopen(base + quoted, timeout=20) as resp:
        return resp.read()


def _base_root():
    """服务的 out_root(conftest 里指向 tmp_path)。用来直接检查磁盘上的残留。"""
    from docanon_core import server

    return server.Handler.out_root


def _roundtrip_conf(base: str) -> dict:
    """上传一份含敏感信息的文本, 用**默认口径**(锚点)脱敏 —— 三套内置默认全类型 anchor。"""
    up = _post(base, "/api/upload", {
        "filename": "note.txt",
        "content_b64": base64.b64encode("原告张三，电话 13812340000。\n".encode()).decode(),
    })
    return _post(base, "/api/anonymize", {"token": up["token"], "config": "default.yaml"})


def __base_root():
    from docanon_core import server

    return server.Handler.out_root


def test_anonymize_reports_that_the_output_is_restorable(base):
    """界面靠这个字段决定要不要给「还原」入口 —— mask/redact 跑出来的必须没有。"""
    resp = _roundtrip_conf(base)
    assert resp["restorable"] is True
    assert resp["restore_token"]
    assert resp["anchors"]


def test_non_anchor_output_is_not_offered_for_restore(base):
    """只有把某类型改成 mask/redact/remove 才会没有锚点 —— 界面不该假装可以还原。"""
    up = _post(base, "/api/upload", {
        "filename": "note.txt",
        "content_b64": base64.b64encode("原告张三，电话 13812340000。\n".encode()).decode(),
    })
    inline = {"strategies": {"DEFAULT": "mask"}, "detectors": {"rule": True}}
    resp = _post(base, "/api/anonymize", {"token": up["token"], "config": inline})
    assert resp["restorable"] is False
    assert resp["restore_token"] is None
    assert resp["anchors"] == {}


def test_restore_puts_the_originals_back(base):
    anon = _roundtrip_conf(base)
    out_name = anon["output_name"]
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": out_name,
        "content_b64": base64.b64encode(data).decode(),
        "expected": anon["anchors"],
    })

    assert resp["total_restored"] > 0
    assert resp["complete"] is True
    assert resp["missing"] == []
    restored = _fetch(base, resp["output_url"])
    assert b"13812340000" in restored   # 原文真的填回去了
    assert b"{{" not in restored       # 没有漏网的锚点


def test_restore_writes_a_report_and_replaces_the_redaction_prefix(base):
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": anon["output_name"],
        "content_b64": base64.b64encode(data).decode(),
        "expected": anon["anchors"],
    })

    assert resp["output_name"].startswith("【还原版】")
    assert "【脱敏版】" not in resp["output_name"]
    report = json.loads(_fetch(base, resp["report_url"]))
    assert report["complete"] is True
    assert report["total_restored"] == resp["total_restored"]


def test_restore_reports_anchors_the_ai_deleted(base):
    """AI 删掉一个锚点: 必须报 missing 且 complete=false, 不能静默交出半成品。"""
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])
    stripped = data.replace(b"{{PHONE_1}}", b"")

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": anon["output_name"],
        "content_b64": base64.b64encode(stripped).decode(),
        "expected": {**anon["anchors"], "{{ORG_1}}": 1},
    })

    assert resp["complete"] is False
    assert "{{ORG_1}}" in resp["missing"]
    assert resp["output_url"]     # 半成品仍然写出, 但标明了 incomplete


def test_restore_reports_anchors_the_ai_invented(base):
    """AI 编出不存在的锚点: 报 unknown, 且**不替换**它。"""
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": anon["output_name"],
        "content_b64": base64.b64encode(data + b"{{PERSON_99}}\n").decode(),
        "expected": anon["anchors"],
    })

    assert "{{PERSON_99}}" in resp["unknown"]
    out = _fetch(base, resp["output_url"])
    assert b"{{PERSON_99}}" in out   # 原样保留, 没有被猜成某个原文


def test_restore_output_lives_in_its_own_directory(base):
    """还原件是未脱敏的原始信息, 不能和可外发的脱敏件混在一个目录里。"""
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": anon["output_name"],
        "content_b64": base64.b64encode(data).decode(),
    })

    assert resp["output_url"].startswith("/restored/")


def test_restore_removes_the_intermediate_uploaded_copy(base):
    """中间文件是用户交回来的原件(含未脱敏内容), 还原完就该删 —— 不留一份没人知道的东西。"""
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": anon["output_name"],
        "content_b64": base64.b64encode(data).decode(),
    })

    rtoken = resp["output_url"].split("/")[2]
    leftovers = [p.name for p in (_base_root() / "restored" / rtoken).iterdir()]
    assert not any(n.startswith("in-") for n in leftovers)





def test_restore_rejects_path_traversal_in_token(base):
    resp = _post(base, "/api/restore", {
        "token": "../../etc",
        "filename": "x.txt",
        "content_b64": base64.b64encode(b"x").decode(),
    })
    assert resp["_status"] == 400
    assert "token" in resp["error"]


def test_restore_rejects_unknown_token(base):
    resp = _post(base, "/api/restore", {
        "token": "deadbeef1234",
        "filename": "x.txt",
        "content_b64": base64.b64encode(b"x").decode(),
    })
    assert resp["_status"] == 404
    assert "映射表" in resp["error"]


def test_restore_strips_a_path_from_the_filename(base):
    """文件名只决定走哪条还原路线, 不参与拼路径 —— `../` 得被剥掉。"""
    anon = _roundtrip_conf(base)
    data = _fetch(base, anon["output_url"])

    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": "../../escaped.txt",
        "content_b64": base64.b64encode(data).decode(),
    })

    assert "/" not in resp["output_name"]
    assert "escaped.txt" in resp["output_name"]


def test_restore_refuses_pdf_with_a_reason(base):
    """pdf 原理上还原不了: 说清楚为什么, 并指到 docx。"""
    anon = _roundtrip_conf(base)
    resp = _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": "x.pdf",
        "content_b64": base64.b64encode(b"%PDF-1.4 fake").decode(),
    })
    assert resp["_status"] == 400
    assert "栅格化" in resp["error"]
    assert "docx" in resp["error"]


def test_failed_restore_leaves_nothing_behind(base):
    """失败要清干净: 半个还原件比没有更危险。"""
    anon = _roundtrip_conf(base)
    _post(base, "/api/restore", {
        "token": anon["restore_token"],
        "filename": "x.pdf",
        "content_b64": base64.b64encode(b"%PDF-1.4 fake").decode(),
    })
    restored_root = _base_root() / "restored"
    leftovers = list(restored_root.iterdir()) if restored_root.is_dir() else []
    assert leftovers == []


# ---------- 整批还原(`/api/restore/batch`) ----------


def _upload_batch(base: str, batch: str, files: dict[str, bytes]) -> None:
    for rel, raw in files.items():
        _post(base, "/api/upload", {
            "filename": rel.split("/")[-1],
            "content_b64": base64.b64encode(raw).decode(),
            "batch": batch,
            "relpath": rel,
        })


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_restore_batch_round_trips_a_whole_folder(base):
    """一批跑完 → AI 改好整批交回 → 逐份还原 + 打包下载, 原文都填回去。"""
    _upload_batch(base, "rb1", {
        "合同/a.txt": "原告 13812340000\n".encode(),
        "说明/b.txt": "被告 13998765432\n".encode(),
    })
    anon = _post(base, "/api/anonymize", {"batch": "rb1", "config": "default.yaml"})
    assert anon["summary"]["ok"] == 2

    items, anchors = [], {}
    for r in anon["results"]:
        assert r["status"] == "ok" and r["restorable"]
        data = _fetch(base, r["output_url"])
        items.append({"filename": r["output_name"], "content_b64": _b64(data)})
        anchors[r["output_name"]] = r["anchors"]

    resp = _post(base, "/api/restore/batch", {
        "token": anon["restore_token"], "items": items, "anchors": anchors,
    })
    assert resp["summary"] == {"total": 2, "ok": 2, "error": 0}
    assert resp["report_url"]

    with urllib.request.urlopen(base + resp["zip_url"], timeout=30) as r:
        raw = r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert len([n for n in zf.namelist() if "【还原版】" in n]) == 2

    for it in resp["results"]:
        restored = _fetch(base, it["output_url"])
        assert b"{{" not in restored          # 没有漏网的锚点
    blob = b"".join(_fetch(base, it["output_url"]) for it in resp["results"])
    assert b"13812340000" in blob and b"13998765432" in blob


def test_restore_batch_one_bad_item_does_not_kill_the_rest(base):
    """一份交错了(pdf 原理上还原不了): 只标这一份失败, 其余照样还原。"""
    _upload_batch(base, "rb2", {"a.txt": "电话 13812340000\n".encode()})
    anon = _post(base, "/api/anonymize", {"batch": "rb2", "config": "default.yaml"})
    r = anon["results"][0]
    data = _fetch(base, r["output_url"])

    resp = _post(base, "/api/restore/batch", {
        "token": anon["restore_token"],
        "items": [
            {"filename": r["output_name"], "content_b64": _b64(data)},
            {"filename": "x.pdf", "content_b64": _b64(b"%PDF-1.4 fake")},
        ],
        "anchors": {r["output_name"]: r["anchors"]},
    })
    assert resp["summary"] == {"total": 2, "ok": 1, "error": 1}
    bad = [x for x in resp["results"] if x["status"] == "error"][0]
    assert bad["filename"] == "x.pdf" and bad["reason"]


def test_restore_batch_without_items_is_400(base):
    anon = _roundtrip_conf(base)
    resp = _post(base, "/api/restore/batch", {"token": anon["restore_token"], "items": []})
    assert resp["_status"] == 400


def test_restore_batch_rejects_path_traversal_in_token(base):
    resp = _post(base, "/api/restore/batch", {
        "token": "../../etc",
        "items": [{"filename": "x.txt", "content_b64": _b64(b"x")}],
    })
    assert resp["_status"] == 400
    assert "token" in resp["error"]


def test_restore_batch_with_no_success_leaves_nothing(base):
    """一份都没成功就不落盘: 空的还原目录只会让人以为有东西。"""
    anon = _roundtrip_conf(base)
    resp = _post(base, "/api/restore/batch", {
        "token": anon["restore_token"],
        "items": [{"filename": "x.pdf", "content_b64": _b64(b"%PDF-1.4 fake")}],
    })
    assert resp["_status"] == 400
    restored_root = _base_root() / "restored"
    assert not restored_root.is_dir() or list(restored_root.iterdir()) == []


def test_restore_batch_zip_missing_dir_is_404(base):
    try:
        urllib.request.urlopen(f"{base}/api/restore/nope/zip", timeout=5)
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:  # pragma: no cover
        raise AssertionError("不存在的还原目录居然给了包")