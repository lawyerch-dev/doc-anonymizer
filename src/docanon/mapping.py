"""全局映射表: 保证同一实体在全文得到一致的替换值, 并支持还原。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


class MappingStore:
    def __init__(self) -> None:
        # entity_type -> {original_text: replacement}
        self._by_type: dict[str, dict[str, str]] = {}
        # 反向: replacement -> original (用于 restore)
        self._reverse: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def get_or_create(
        self, entity_type: str, original: str, factory: Callable[[int], str]
    ) -> str:
        table = self._by_type.setdefault(entity_type, {})
        if original in table:
            return table[original]
        self._counters[entity_type] = self._counters.get(entity_type, 0) + 1
        replacement = factory(self._counters[entity_type])
        table[original] = replacement
        self._reverse[replacement] = original
        return replacement

    def to_dict(self) -> dict:
        return {
            "by_type": self._by_type,
            "reverse": self._reverse,
            "counters": self._counters,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "MappingStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls()
        store._by_type = data.get("by_type", {})
        store._reverse = data.get("reverse", {})
        store._counters = data.get("counters", {})
        return store
