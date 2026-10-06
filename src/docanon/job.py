"""一份脱敏任务的账本: 一组输入 → 一组产物 + 可续跑的状态。

断点续跑的依据只有 `manifest.json` 与 `mapping.json`, 所以它们**每处理完一个文件就落盘**,
写的时候先写临时文件再 os.replace —— 账本半截损坏比没账本更危险(它会让你以为跑过了)。

判定"这个文件已经处理过"必须同时要求产物文件仍在: 账本说做过、文件却不在了,
那就是漏脱敏的入口, 必须重跑。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import Config
from .mapping import MappingStore
from .pipeline import prepare_detectors, process_file


def _write_json_atomic(path: Path, payload: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class RedactionJob:
    """一次 run 的账本与执行器。

    `out_dir` 就是这份任务的身份: 续跑要求同一个输入目录配同一个 `-o`
    (账本里的 source 与产物路径都是相对它记的)。
    """

    def __init__(self, out_dir: Path, config: Config, resume: bool = False) -> None:
        self.out_dir = Path(out_dir)
        self.config = config
        self.resume = resume
        self.mapping_path = self.out_dir / "mapping.json"
        self.manifest_path = self.out_dir / "manifest.json"
        self.store = MappingStore()
        self.entries: dict[str, dict] = {}
        self.inputs: list[str] = []
        if self.manifest_path.exists() or self.mapping_path.exists():
            self._adopt_existing_ledger()

    # ---------- 账本读写 ----------
    def _adopt_existing_ledger(self) -> None:
        """读旧账本; 读不出来就拒绝跑, 绝不静默当成空白目录重来。"""
        try:
            if self.mapping_path.exists():
                self.store = MappingStore.load(self.mapping_path)
            if self.manifest_path.exists():
                data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                for entry in data.get("files", []):
                    if isinstance(entry, dict) and entry.get("source"):
                        self.entries[entry["source"]] = entry
                self.inputs = list(data.get("inputs", []))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"输出目录里已有账本但读不出来: {exc}；"
                "为了不覆盖上一次的记录, 本次未执行。请换一个空的 -o 目录。"
            ) from exc

    def is_done(self, rel: str) -> bool:
        """续跑时可否跳过: 上次 ok、产物列表非空、且这些文件现在仍然在。"""
        if not self.resume:
            return False
        entry = self.entries.get(rel)
        if not entry or entry.get("status") != "ok":
            return False
        outputs = entry.get("outputs") or []
        return bool(outputs) and all(Path(p).exists() for p in outputs)

    def record(self, rel: str, entry: dict) -> None:
        """记一个文件并立刻落盘 —— 崩在这一条之后也保得住已经做完的部分。"""
        self.entries[rel] = entry
        self.save()

    def note_input(self, target: Path) -> None:
        text = str(target)
        if text not in self.inputs:
            self.inputs.append(text)

    def save(self) -> None:
        self.store.save(self.mapping_path)
        entries = list(self.entries.values())
        _write_json_atomic(self.manifest_path, {
            "inputs": self.inputs,
            "files": entries,
            "totals": self.totals(),
            "summary": {
                "processed": sum(1 for e in entries if e["status"] == "ok"),
                "errors": sum(1 for e in entries if e["status"] == "error"),
                "unsupported": sum(1 for e in entries if e["status"] == "unsupported"),
            },
        })

    def totals(self) -> dict[str, int]:
        total: dict[str, int] = {}
        for entry in self.entries.values():
            for kind, count in (entry.get("counts") or {}).items():
                total[kind] = total.get(kind, 0) + count
        return total

    # ---------- 执行 ----------
    def prepare(self) -> None:
        """引擎预检: 少一层检测就别说这份文档脱过敏。"""
        prepare_detectors(self.config)

    def covers_input(self, target: Path) -> bool:
        return str(target) in self.inputs

    def run_file(self, path: Path, rel: Path) -> dict:
        try:
            res = process_file(path, self.out_dir, self.config, self.store, rel=rel)
        except Exception as exc:  # noqa: BLE001
            return {"source": str(rel), "status": "error", "error": str(exc)}
        return {
            "source": str(rel),
            "status": "ok",
            "outputs": res.outputs,
            "counts": res.entity_counts,
        }

    def pending_output_count(self) -> int:
        """账本里 `ok` 但产物已经不在的条目数 —— 这些会在续跑时重来。"""
        stale = 0
        for entry in self.entries.values():
            if entry.get("status") != "ok":
                continue
            outputs = entry.get("outputs") or []
            if not outputs or not all(Path(p).exists() for p in outputs):
                stale += 1
        return stale

    def tally(self) -> dict:
        entries = list(self.entries.values())
        return {
            "processed": sum(1 for e in entries if e["status"] == "ok"),
            "errors": sum(1 for e in entries if e["status"] == "error"),
            "unsupported": sum(1 for e in entries if e["status"] == "unsupported"),
        }
