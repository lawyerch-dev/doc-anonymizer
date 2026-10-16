"""全局映射表: 保证同一实体在全文得到一致的替换值, 并支持还原。

`remove` 策略的替换值是空串: 它只进正向表(原文 -> ""), **绝不进反向表** ——
空串不是可定位的锚点, 拿去 `str.replace` 会把原文插到每个字符之间(实测过的灾难)。
还原只认非空替换值, 见 `restorable_items()`。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..atomic import write_json


class MappingStore:
    def __init__(self) -> None:
        # entity_type -> {original_text: replacement}
        self._by_type: dict[str, dict[str, str]] = {}
        # 反向: replacement -> original (用于 restore); 不含空串
        self._reverse: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        # replacement -> 累计替换次数。还原时用来对账: 文档里出现的次数少于这里,
        # 说明有一部分锚点被 AI 删掉或改坏了 —— 静默少还原等于交出一份半成品。
        self._uses: dict[str, int] = {}

    def get_or_create(
        self, entity_type: str, original: str, factory: Callable[[int], str]
    ) -> str:
        table = self._by_type.setdefault(entity_type, {})
        if original in table:
            return table[original]
        self._counters[entity_type] = self._counters.get(entity_type, 0) + 1
        replacement = factory(self._counters[entity_type])
        table[original] = replacement
        if replacement:
            self._reverse[replacement] = original
            self._uses.setdefault(replacement, 0)
        return replacement

    def note_use(self, replacement: str) -> None:
        """记一次"这个替换值被真的写进产物了"。"""
        if replacement:
            self._uses[replacement] = self._uses.get(replacement, 0) + 1

    def use_counts(self) -> dict[str, int]:
        return dict(self._uses)

    def reverse_table(self) -> dict[str, str]:
        """反向表的副本: 替换值 → 原文, 不含空串(remove 策略)。"""
        return dict(self._reverse)

    def restorable_items(self) -> list[tuple[str, str]]:
        """可用于还原的 (替换值, 原文), 长的优先(避免短值先吃掉长值的一部分)。

        读历史 mapping.json 时也会过滤掉空键: 旧文件里可能已经躺着 `{"": 原文}`。
        """
        return sorted(
            [(r, o) for r, o in self._reverse.items() if r],
            key=lambda kv: -len(kv[0]),
        )

    def unrestorable_count(self) -> int:
        """映射表里还原不了的**原文**条数(都是 remove 策略: 替换值为空串)。

        正向表是权威(新版只在那里留痕); 老 mapping.json 可能只在反向表里留了个空键,
        两边都收一遍再按原文去重, 免得同一条老记录被数成两条。
        """
        empties = {
            original
            for table in self._by_type.values()
            for original, repl in table.items()
            if not repl
        }
        empties |= {original for repl, original in self._reverse.items() if not repl}
        return len(empties)

    def to_dict(self) -> dict:
        return {
            "by_type": self._by_type,
            "reverse": self._reverse,
            "counters": self._counters,
            "uses": self._uses,
        }

    def save(self, path: str | Path) -> None:
        write_json(path, self.to_dict())   # 原子写: 半截映射表比没映射表更危险

    @classmethod
    def load(cls, path: str | Path) -> "MappingStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls()
        store._by_type = data.get("by_type", {})
        store._reverse = data.get("reverse", {})
        store._counters = data.get("counters", {})
        store._uses = data.get("uses", {})
        return store
