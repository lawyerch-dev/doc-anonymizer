"""`Block.locator` 与 `ExtractedDoc.meta` 的**键名**约定 —— 唯一出处。

抽取器(引擎或 core)往这两个 dict 里塞键, 检测/回写再按这些键读。键名若只在写入方与读取方
各自靠约定对齐, 引擎改个名字, core 就**静默失效** —— 而 `tests/test_architecture.py` 用 AST
锁的是 import 方向, 锁不住数据契约。所以键名集中在这里, 两侧都引用: 改名只动这一处, 不一致会
变成 ImportError/NameError, 而不是悄悄少读一份数据。

只依赖标准库(本模块不许 import 别的东西), 与 contract 其余部分一样可整块搬走。
"""
from __future__ import annotations

# --- Block.locator: 定位信息。**键的存在**决定回写走哪条路(writers 按它分派) ---
LINE = "line"              # 纯文本行号(0 起)
PARAGRAPH = "paragraph"    # 段落遍历序号(空段落也占位)
PAGE = "page"              # PDF 页号(0 起)
BBOX = "bbox"              # 图片/扫描件里的框 [x0, y0, x1, y1]
ROW = "row"                # CSV 行(1 起)
COL = "col"                # CSV 列(1 起)
SHEET = "sheet"            # xlsx 工作表名
CELL = "cell"              # xlsx 单元格坐标(如 "B3")
SCORE = "score"            # OCR 置信度(仅参考, 不参与分派)

# --- ExtractedDoc.meta ---
FORMAT = "format"                      # 取值见下面 FORMAT_*, 决定回写器
NEEDS_IMAGE = "needs_image_redaction"  # 命中要按图片涂黑回写
SCANNED_IMAGES = "_scanned_images"     # 扫描页的渲染图, 供栅格化回写
SCANNED_PAGES = "scanned_pages"        # 扫描页页号列表(仅记录)
CONVERTED_FROM = "converted_from"      # 旧格式转换来的源扩展名
OUT_EXT = "out_ext"                    # 产物强制扩展名
CONVERT_WORKDIR = "_convert_workdir"   # 旧格式转换的临时工作目录(用完由 process_file 清)

# `FORMAT` 的取值
FORMAT_DOCX = "docx"
FORMAT_TEXT = "text"
FORMAT_TABLE = "table"
FORMAT_PDF = "pdf"
FORMAT_IMAGE = "image"
