#!/usr/bin/env python3
"""把仓库里的 markdown 同步成 Starlight 的内容(src/content/docs/, 构建产物不提交)。

为什么要有这一步: Starlight 的内容必须带 frontmatter(title 必填), 而仓库里的文档是给人读的
纯 markdown(一级标题就是标题)。这里只做三件事, 源始终是仓库那些文件:
  1. 按 content-manifest.json 从一级标题取出 title, 注入 frontmatter;
  2. 把 .md 相对链接改写成站内路由(/slug/), 否则点过去 404;
  3. 按 manifest 的 group 落到 src/content/docs/<group>/<slug>.md(侧栏按目录自动分组)。

清单里指向的文件不存在 → 直接报错退出(不许静默少一页)。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
REPO = SITE.parent.parent
OUT = SITE / "src" / "content" / "docs"

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
H1 = re.compile(r"^#\s+(.+)$", re.M)


def read_page(entry: dict, file_to_route: dict[str, str]) -> str:
    src = REPO / entry["file"]
    if not src.is_file():
        sys.exit(f"错误: 清单里的文件不存在: {entry['file']}")
    text = FRONTMATTER.sub("", src.read_text(encoding="utf-8"))
    h1 = H1.search(text)
    text = H1.sub("", text, count=1).lstrip("\n")          # 标题进 frontmatter, 正文别再重复
    title = entry.get("title") or (h1.group(1).strip() if h1 else src.stem)

    def to_route(match: re.Match[str]) -> str:
        href = match.group(1)
        if re.match(r"^(https?:|mailto:|#|/)", href):
            return match.group(0)
        target, _, anchor = href.partition("#")
        if not target.endswith(".md"):
            return match.group(0)
        try:
            rel = (src.parent / target).resolve().relative_to(REPO).as_posix()
        except ValueError:
            return match.group(0)
        route = file_to_route.get(rel)          # 清单里的 group/slug, 不是文件名
        if route is None:
            return match.group(0)
        suffix = f"#{anchor}" if anchor else ""
        return f"](/{route}/{suffix})"

    text = re.sub(r"\]\(([^)\s]+)\)", to_route, text)

    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"description: {json.dumps(entry.get('description', ''), ensure_ascii=False)}\n"
        "---\n\n" + text.strip() + "\n"
    )


def main() -> None:
    manifest = json.loads((SITE / "content-manifest.json").read_text(encoding="utf-8"))
    pages = manifest["pages"]
    file_to_route = {p["file"]: f"{p['group']}/{p['slug']}" for p in pages}

    if OUT.exists():
        for old in OUT.rglob("*.md"):
            old.unlink()
    written = []
    for entry in pages:
        dest = OUT / entry["group"] / f"{entry['slug']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(read_page(entry, file_to_route), encoding="utf-8")
        written.append(dest.relative_to(SITE).as_posix())

    # 侧栏也由同一份清单生成: 避免 astro.config 里再抄一遍组与顺序
    groups: dict[str, list[dict[str, str]]] = {}
    for entry in pages:
        groups.setdefault(entry["group"], []).append(
            {"label": entry["title"], "slug": f"{entry['group']}/{entry['slug']}"}
        )
    label_of = {"start": "开始", "dev": "开发", "other": "其他"}
    sidebar = [{"label": label_of.get(g, g), "items": items} for g, items in groups.items()]
    sidebar_ts = SITE / "src" / "sidebar.generated.mjs"
    sidebar_ts.write_text(
        "// 由 scripts/sync-content.py 从 content-manifest.json 生成, 不要手改\n"
        "export default " + json.dumps(sidebar, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"同步 {len(written)} 页 → {OUT.relative_to(SITE)}/")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
