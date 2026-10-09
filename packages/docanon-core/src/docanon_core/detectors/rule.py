"""正则规则检测器: 覆盖强规则的 PII 与凭证。召回优先。"""
from __future__ import annotations

import re

from docanon_contract import Block, Detection, Detector, Span

# (实体类型, 正则)。顺序影响同类重叠时的取舍, 长的/更具体的放前面。
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 身份证: 18 位(末位可为 X)
    ("ID_CARD", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")),
    # 护照: E/G + 8 位(旧版 G 开头, 现行为 E 开头)
    ("PASSPORT", re.compile(r"(?<![0-9A-Za-z])[EG]\d{8}(?![0-9A-Za-z])")),
    # 车牌: 省份简称 + 字母 + 5 位(新能源 6 位)。字母表里没有 I/O, 后两位可用"挂学警港澳"
    ("PLATE", re.compile(
        r"(?<![0-9A-Za-z])[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]"
        r"[A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳](?![0-9A-Za-z])"
    )),
    # 统一社会信用代码: 18 位字母数字
    ("USCC", re.compile(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![0-9A-Z])")),
    # 银行卡: 16-19 位数字(避免与身份证重叠由 resolve 处理)。
    # 真实合同/单据里的卡号几乎都写成 4 位一组("6222 0212 3456 7890 123" / "6222-0212-3456-7890"),
    # 只认连续数字会整类漏掉 —— 那是隐私泄漏, 不是漏检偏好。
    # 分组形态要求"4 位一组共 4 组", 免得把 "2026 03 01 2026 03 01" 这类日期串当卡号。
    ("BANK_CARD", re.compile(
        r"(?<!\d)(?:\d{16,19}|\d{4}(?:[ -]\d{4}){3}(?:[ -]\d{1,3})?)(?!\d)"
    )),
    # 手机号(中国大陆)
    ("PHONE", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    # 固定电话: 区号 + 7~8 位。前后不许贴数字或字母, 免得吃进统一社会信用代码/银行卡里
    ("PHONE", re.compile(r"(?<![0-9A-Za-z])0\d{2,3}[-\s]?\d{7,8}(?!\d)")),
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

    def capabilities(self) -> list[str]:
        return sorted({t for t, _ in _PATTERNS})

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
