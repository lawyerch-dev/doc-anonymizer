"""脱敏策略: 给定实体类型与原文, 生成替换值。

一致性由 MappingStore 保证: 同一 (类型, 原文) 只会生成一次替换值。
"""
from __future__ import annotations

import hashlib
from typing import Callable

from .mapping import MappingStore

# ---- 假名素材池(可替换为 LLM 生成) ----
_SURNAMES = ["林", "沈", "顾", "苏", "程", "陆", "许", "江", "叶", "秦", "温", "崔"]
_GIVEN = ["芳", "宁", "舟", "澜", "屿", "琛", "玥", "然", "禾", "青", "序", "澄"]
_ORG_A = ["华", "泰", "锐", "联", "远", "恒", "中", "嘉", "擎", "知"]
_ORG_B = ["信", "创", "达", "腾", "晟", "源", "科", "云", "诚", "越"]
_ORG_C = ["集团", "科技", "有限公司", "实业", "信息", "智能"]


def _digest(key: str, mod: int) -> int:
    return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % mod


def _person(n: int, original: str) -> str:
    i = _digest(original, len(_SURNAMES))
    j = _digest(original + "g", len(_GIVEN))
    return _SURNAMES[i] + _GIVEN[j]


def _org(n: int, original: str) -> str:
    a = _ORG_A[_digest(original, len(_ORG_A))]
    b = _ORG_B[_digest(original + "o", len(_ORG_B))]
    c = _ORG_C[_digest(original + "c", len(_ORG_C))]
    return f"{a}{b}{c}"


def _mask(entity_type: str, original: str) -> str:
    s = original
    n = len(s)
    if entity_type == "PHONE" and n >= 7:
        return f"{s[:3]}****{s[-4:]}"
    if entity_type == "ID_CARD" and n >= 10:
        return f"{s[:6]}{'*' * (n - 10)}{s[-4:]}"
    if entity_type == "BANK_CARD" and n >= 4:
        return f"{'*' * (n - 4)}{s[-4:]}"
    if entity_type == "EMAIL" and "@" in s:
        local, domain = s.split("@", 1)
        return f"{local[:1]}***@{domain}"
    if entity_type == "USCC" and n >= 8:
        return f"{s[:4]}{'*' * (n - 8)}{s[-4:]}"
    if n <= 2:
        return "*" * n
    return f"{s[:1]}{'*' * (n - 2)}{s[-1:]}"


def _placeholder(entity_type: str, n: int) -> str:
    return f"<{entity_type}_{n}>"


def _redact(n: int, original: str) -> str:
    """整体盖成 **: 不泄漏长度、不产出像真的内容。默认口径。"""
    return "**"


def make_replacer(entity_type: str, strategy: str) -> Callable[[int, str], str]:
    if strategy == "pseudonym":
        if entity_type == "ORG":
            return _org
        if entity_type == "PERSON":
            return _person
        # 其他类型无专用假名, 退化为占位符
        return lambda n, original: _placeholder(entity_type, n)
    if strategy == "redact":
        return _redact
    if strategy == "mask":
        return lambda n, original: _mask(entity_type, original)
    if strategy == "remove":
        return lambda n, original: ""
    # placeholder (默认)
    return lambda n, original: _placeholder(entity_type, n)


def replacement_for(
    store: MappingStore, entity_type: str, original: str, strategy: str
) -> str:
    factory = make_replacer(entity_type, strategy)
    return store.get_or_create(entity_type, original, lambda n: factory(n, original))


def apply_spans(text: str, replacements: list[tuple[int, int, str]]) -> str:
    """replacements: [(start, end, replacement)], 按位置从后往前替换。"""
    for start, end, repl in sorted(replacements, key=lambda x: x[0], reverse=True):
        text = text[:start] + repl + text[end:]
    return text
