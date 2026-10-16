"""锚点语法 `{{TYPE_N}}`: **唯一一处**定义 —— 生产、匹配、规范化都从这里取。

生产在 `strategies`(脱敏那一侧), 匹配与规范化在 `restorers`(还原那一侧)。两边一旦对不上,
还原会**静默失败** —— 漏还原等于交出一份半成品, 是全项目最不该出现的一种失败。所以语法只写一遍。

另有老版 `placeholder` 策略产出的 `<TYPE_N>`: 历史 `mapping.json` 里还躺着, 仍要认得。
"""
from __future__ import annotations

import re

# 匹配时**故意宽松**: AI 可能在锚点两侧加空格、改大小写、套 markdown 强调号或反引号,
# 甚至把 {{ 转义成 HTML 实体。这些都是"同一个锚点被包了一层", 不该判成还原失败。
# 匹配出来后再用规范化形式(大写、去掉内部空白)去查表 —— 查不到就是未知锚点, 不猜。
ANCHOR_RE = re.compile(r"\{\{\s*([A-Za-z_]+)\s*_(\d+)\s*\}\}")
# 老版 placeholder 策略: `<TYPE_N>`。
LITERAL_RE = re.compile(r"<([A-Za-z_]+)_(\d+)>")


def format_anchor(entity_type: str, n: int) -> str:
    """生产: 可寻址锚点 `{{TYPE_N}}`(为什么用双花括号见 `strategies._anchor`)。"""
    return f"{{{{{entity_type}_{n}}}}}"


def normalize_anchor(entity_type: str, index: str) -> str:
    """匹配出来的组 → 规范锚点(类型大写、去内部空白), 用来查表。"""
    return f"{{{{{entity_type.strip().upper()}_{int(index)}}}}}"


def anchor_key(value: str) -> str | None:
    """把一个**替换值**规范成查表的锚点键; 不是锚点(假名/打码/空串)返回 None。"""
    text = value.strip()
    m = ANCHOR_RE.fullmatch(text) or LITERAL_RE.fullmatch(text)
    return normalize_anchor(m.group(1), m.group(2)) if m else None


def is_anchor(value: str) -> bool:
    """这个替换值是不是可寻址锚点(能被 restore 认出来)。

    账本只记锚点 —— `mask`/`redact` 的替换值虽也进映射表, 但还原不了, 记进去只会让对账
    报告把一堆注定还原不回来的东西报成「缺失」。
    """
    return anchor_key(value) is not None
