#!/usr/bin/env python3
"""把 shadcn CLI 生成的 `@/...` 导入改成相对路径, 并生成组件清单。

为什么要改: `@/` 是 shadcn 的宿主别名。kit 是共享包, 不能让每个消费方(website、将来的 apps/web)
都去配 `@` → kit 源码(而且消费方自己的 `@/` 多半指的是它自己的 src)。改成相对路径后, 包开箱即用。

幂等: 重复跑不会改坏; `--check` 只检查不写(CI/测试可用)。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

KIT = pathlib.Path(__file__).resolve().parent.parent
SRC = KIT / "src"
IMPORT = re.compile(r'(from\s+)"@/([^"]+)"')

check_only = "--check" in sys.argv


def to_relative(source_file: pathlib.Path, target: str) -> str:
    """src 下的目标模块 → 相对当前文件的路径(不带扩展名)"""
    here = source_file.parent
    dest = SRC / target
    rel = pathlib.PurePosixPath(dest.relative_to(SRC).as_posix()).parent
    # 用相对路径表达: 先算出到 SRC 的关系
    up = len(here.relative_to(SRC).parts)
    prefix = "../" * up
    return prefix + target


changed = []
for path in sorted(SRC.rglob("*.ts*")):
    text = path.read_text(encoding="utf-8")
    new = IMPORT.sub(lambda m: f'{m.group(1)}"{to_relative(path, m.group(2))}"', text)
    if new != text:
        changed.append(path.relative_to(KIT).as_posix())
        if not check_only:
            path.write_text(new, encoding="utf-8")

# 生成清单(从 registry.lock.json, 便于文档/测试核对)
lock = json.loads((KIT / "registry.lock.json").read_text(encoding="utf-8"))
manifest = {"source": "https://velora.colorlib.com/r/registry.json (MIT, © Colorlib)", "items": []}
for item in lock["items"]:
    for f in item["files"]:
        manifest["items"].append(
            {
                "name": item["name"],
                "type": item["type"].replace("registry:", ""),
                "title": item.get("title", item["name"]),
                "description": item.get("description", ""),
                "file": f["path"],
            }
        )
if not check_only:
    (SRC / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"导入已规范化: {len(changed)} 个文件" if not check_only else f"待规范化的文件: {len(changed)}")
print(f"清单: {len(manifest['items'])} 项 (组件 {sum(1 for i in manifest['items'] if i['type']=='ui')} / blocks {sum(1 for i in manifest['items'] if i['type']=='block')})")
if check_only and changed:
    sys.exit(1)
