"""正则规则检测器: 覆盖强规则的 PII 与凭证。召回优先。"""
from __future__ import annotations

import re

from ..models import Block, Detection, Span
from .base import Detector

# (实体类型, 正则)。顺序影响同类重叠时的取舍, 长的/更具体的放前面。
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 身份证: 18 位(末位可为 X)
    ("ID_CARD", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")),
    # 统一社会信用代码: 18 位字母数字
    ("USCC", re.compile(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![0-9A-Z])")),
    # 银行卡: 16-19 位数字(避免与身份证重叠由 resolve 处理)
    ("BANK_CARD", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
    # 手机号(中国大陆)
    ("PHONE", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    # 邮箱
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # 金额(带货币符号或"元/万/亿"单位)
    ("AMOUNT", re.compile(r"(?:[¥￥$]\s*\d[\d,]*(?:\.\d+)?)|(?:\d[\d,]*(?:\.\d+)?\s*(?:万元|亿元|万|亿|元))")),
    # IPv4
    ("IP", re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")),
    # 常见密钥/凭证
    ("SECRET", re.compile(r"(?i)\b(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-]{16,})\b")),
]


class RuleDetector(Detector):
    name = "rule"

    def detect(self, block: Block) -> list[Detection]:
        out: list[Detection] = []
        text = block.text
        for entity_type, pattern in _PATTERNS:
            for m in pattern.finditer(text):
                out.append(
                    Detection(
                        span=Span(m.start(), m.end(), m.group()),
                        entity_type=entity_type,
                        source="rule",
                        confidence=1.0,
                    )
                )
        return out
