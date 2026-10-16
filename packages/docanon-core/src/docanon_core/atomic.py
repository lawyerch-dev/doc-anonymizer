"""原子落盘: 先写同目录临时文件再 `os.replace` —— 半截文件比没文件更危险。

账本(`manifest.json` / `mapping.json`)、界面偏好、用户配置都走这里, 不许各自再写一份
`tmp + replace`。`os.replace` 在同一分区上是原子的, 读者要么看到旧内容、要么看到新内容。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: str | Path, payload: Any, *, trailing_newline: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    write_text(path, text + ("\n" if trailing_newline else ""))
