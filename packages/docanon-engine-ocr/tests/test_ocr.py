"""OCR 引擎自己的测试: 不经过 core, 也不需要 app。

需要 rapidocr(没装就 skip —— 但不能静默 skip 掉整个 OCR 回归: 仓库的 .venv 里是装好的)。
"""
from __future__ import annotations

import pathlib

import pytest

from docanon_engine_ocr import ImageExtractor, run_ocr

NON_LATIN_FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


def _image_with_text(text: str, size: int = 40) -> pathlib.Path:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(NON_LATIN_FONT, size)
    img = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(img).text((20, 30), text, fill="black", font=font)
    return img


def test_image_extractor_declares_its_extensions():
    ex = ImageExtractor()
    assert ex.name == "ocr_image"
    assert ".png" in ex.extensions and ".jpg" in ex.extensions
    assert set(ex.capabilities()) == set(ex.extensions)
    assert ex.ready() is None


def test_run_ocr_returns_text_and_bbox():
    pytest.importorskip("rapidocr")
    img = _image_with_text("身份证 110101199003071234")
    items = run_ocr(img)

    assert items, "合成图片上一个字都没识别出来"
    assert all("text" in it and "bbox" in it for it in items)
    joined = "".join(it["text"] for it in items)
    assert any(ch.isdigit() for ch in joined), f"识别结果里没有数字: {joined!r}"
    x0, y0, x1, y1 = items[0]["bbox"]
    assert x0 < x1 and y0 < y1, "bbox 应该是有序的 (left, top, right, bottom)"


def test_extract_from_file_uses_ocr_when_no_text_layer(tmp_path):
    pytest.importorskip("rapidocr")
    path = tmp_path / "scan.png"
    _image_with_text("联系电话 13812340000").save(path)

    doc = ImageExtractor().extract(path)

    assert doc.meta["format"] == "image"
    assert doc.image_path and doc.blocks, "图片抽取应该给出 blocks(带 bbox)"
    assert all("bbox" in b.locator for b in doc.blocks)
