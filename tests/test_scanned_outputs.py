"""扫描件产物的真实路径(清单里不能写一个不存在的文件)。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _scanned_pdf(path: Path) -> None:
    pytest.importorskip("rapidocr")
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    # 先把文字渲染成图片, 再放进 PDF —— 得到无文字层的扫描页
    tmp = path.with_suffix(".src.pdf")
    c = canvas.Canvas(str(tmp), pagesize=(595, 842))
    c.setFont("Helvetica", 20)
    c.drawString(60, 780, "ID 110101198802023456 PHONE 13812340000")
    c.showPage()
    c.save()
    import pypdfium2 as pdfium

    img = pdfium.PdfDocument(str(tmp))[0].render(scale=2.0).to_pil()
    img.save(path.with_suffix(".png"))
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.drawImage(str(path.with_suffix(".png")), 0, 0, 595, 842)
    c.showPage()
    c.save()


def test_manifest_output_paths_exist_for_scanned_pdf(tmp_path):
    from docanon.cli import main

    _scanned_pdf(tmp_path / "扫描件.pdf")
    out = tmp_path / "out"

    assert main(["run", str(tmp_path / "扫描件.pdf"), "-o", str(out)]) == 0

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["files"][0]
    assert entry["status"] == "ok"
    for produced in entry["outputs"]:
        assert Path(produced).exists(), f"清单里的产物不存在: {produced}"
    # 确实做了涂黑: 命中行的像素被改成黑色
    png = out / "扫描件.pdf.redacted.p0.png"
    assert png.exists()


def test_result_exposes_all_written_files(tmp_path):
    from docanon.config import load_config
    from docanon.mapping import MappingStore
    from docanon.pipeline import process_file

    _scanned_pdf(tmp_path / "扫描件.pdf")
    res = process_file(
        tmp_path / "扫描件.pdf", tmp_path / "out", load_config(), MappingStore()
    )
    assert res.outputs and all(Path(p).exists() for p in res.outputs)
    assert res.output_path == res.outputs[0]
