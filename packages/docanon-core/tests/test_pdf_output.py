"""PDF 产物的安全性质与"只处理命中的页"。

两条硬性质:
1. **命中的页不保留可提取文字** —— 给文字层盖黑块不等于脱敏(原文仍可复制/搜索), 所以命中页必须
   栅格化。这条是安全保证, 谁把它"优化"回保留文字层, 这里就红。
2. **没命中的页原样保留** —— 不陪着重渲染(矢量文字还在、体积不变), 50 页的合同只有 1 页含敏感信息时
   不该整份变成位图。
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pypdfium2")

SECRET = "110101199003071234"      # 身份证规则命中
PHONE = "13812340000"
CLEAN = "Quarterly logistics summary, no personal data on this page."


def _pdf(path: Path, *pages: str) -> Path:
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=(595, 842))
    for line in pages:
        c.setFont("Helvetica", 16)
        c.drawString(60, 780, line)
        c.showPage()
    c.save()
    return path


def _text_of(pdf: Path, pno: int) -> str:
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(str(pdf))[pno].get_textpage().get_text_range()


def _render(pdf: Path, pno: int = 0, scale: float = 2.0):
    import numpy as np
    import pypdfium2 as pdfium

    return np.asarray(pdfium.PdfDocument(str(pdf))[pno].render(scale=scale).to_pil().convert("L"))


def _redact(src: Path, out_dir: Path):
    from docanon_core.config import load_config
    from docanon_core.redaction.mapping import MappingStore
    from docanon_core.pipeline import process_file

    return process_file(src, out_dir, load_config(), MappingStore())


def test_page_with_hits_keeps_no_text_page_without_hits_keeps_its_own(tmp_path):
    src = _pdf(tmp_path / "两页.pdf", f"ID {SECRET}", CLEAN)
    res = _redact(src, tmp_path / "out")
    out = Path(res.output_path)

    assert res.entity_counts.get("ID_CARD") == 1
    assert SECRET not in _text_of(out, 0), "命中页还留着可提取的原文 = 没脱敏"
    assert _text_of(out, 0).strip() == "", "命中页应整页栅格化(文字层消失)"
    assert CLEAN in _text_of(out, 1), "没命中的页不该陪着重渲染成位图"
    assert SECRET not in _text_of(out, 1)


def test_document_without_any_hits_stays_a_real_pdf(tmp_path):
    src = _pdf(tmp_path / "干净.pdf", CLEAN, CLEAN)
    res = _redact(src, tmp_path / "out")
    out = Path(res.output_path)

    assert res.entity_counts == {}
    assert len(_text := [_text_of(out, i) for i in range(2)]) == 2
    assert all(CLEAN in t for t in _text)


def test_black_box_covers_exactly_the_sensitive_span(tmp_path):
    """涂黑位置必须压住原文字符框: 矩阵/坐标换算错了会"看着脱敏、其实漏在外面"。"""
    import pypdfium2 as pdfium

    src = _pdf(tmp_path / "一页.pdf", f"ID {SECRET} OK")
    page = pdfium.PdfDocument(str(src))[0]
    text = page.get_textpage().get_text_range()
    start = text.index(SECRET)
    boxes = [page.get_textpage().get_charbox(i) for i in range(start, start + len(SECRET))]
    left = min(b[0] for b in boxes)
    bottom = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    top = max(b[3] for b in boxes)
    page_w, page_h = page.get_size()

    res = _redact(src, tmp_path / "out")
    scale = 2.0
    img = _render(Path(res.output_path), scale=scale)
    # PDF 坐标原点在左下, 位图原点在左上
    x0, x1 = int(left * scale) + 2, int(right * scale) - 2
    y0, y1 = int((page_h - top) * scale) + 2, int((page_h - bottom) * scale) - 2
    region = img[y0:y1, x0:x1]

    assert region.size, "字符框换算出来的区域是空的, 测试本身有问题"
    assert region.mean() < 80, f"敏感片段所在区域没被涂黑(均值 {region.mean():.0f})"
    # 同一页其余部分仍是白纸黑字: 涂黑不能糊满整页
    assert img.mean() > 200, "整页都被涂黑了"
