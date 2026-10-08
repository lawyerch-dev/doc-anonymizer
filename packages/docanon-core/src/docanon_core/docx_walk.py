"""DOCX 正文的两层遍历: 段落有哪些、段落里的文字槽有哪些。

抽取和回写**必须**用同一套遍历: 前者按它算字符偏移, 后者按它把替换值写回去。
各写一套就一定会错位, 而错位的后果同时是漏脱敏(目标字没被换掉)与损坏(旁边的字被换成替换值)。

python-docx 的 `paragraph.text` 含超链接里的文字, 但 `paragraph.runs` 只认段落的直接子
`w:r` —— 拿后者套前者的偏移就是这个错位的来源。这里两个视图都自己提供, 顺序保证一致。
"""
from __future__ import annotations

from typing import Iterator

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

# 会往下走的容器: 表格(含嵌套)、单元格、内容控件。没有 w:p 以外的东西被漏掉。
_BLOCK_CONTAINERS = {qn(t) for t in ("w:tbl", "w:tr", "w:tc", "w:sdt", "w:sdtContent")}

# 段落里能装文字的东西。w:r 的直接子项以外都要显式列出来, 否则那些字既抽不到也改不了:
#   hyperlink=点得开的链接(Word 里邮箱/网址默认长这样)、ins=修订插入、smartTag、sdt=行内控件、
#   fldSimple=简单域(REF/PAGE 这类域的显示文字)、moveTo=移动的修订。
_TEXT_CONTAINERS = {
    qn(t)
    for t in ("w:hyperlink", "w:ins", "w:smartTag", "w:sdt", "w:sdtContent", "w:fldSimple", "w:moveTo")
}


def iter_paragraphs(document) -> Iterator[Paragraph]:
    """正文里的段落, 按文档顺序: 顶层、表格单元格、嵌套表格、内容控件里的都算。

    页眉/页脚/脚注/文本框不在 body 里, 因此仍不抽取(见 README 的已知限制)。
    """
    yield from _walk_paragraphs(document.element.body, document)


def _walk_paragraphs(element, parent) -> Iterator[Paragraph]:
    for child in element.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag in _BLOCK_CONTAINERS:
            yield from _walk_paragraphs(child, parent)


def text_runs(paragraph: Paragraph) -> list[Run]:
    """段落里的文字槽, 按文档顺序 —— 拼接起来就是这段的可见文字。"""
    return [Run(element, paragraph) for element in _walk_runs(paragraph._p)]


def _walk_runs(element) -> Iterator:
    for child in element.iterchildren():
        if child.tag == qn("w:r"):
            yield child
        elif child.tag in _TEXT_CONTAINERS:
            yield from _walk_runs(child)


def paragraph_text(paragraph: Paragraph) -> str:
    return "".join(run.text for run in text_runs(paragraph))
