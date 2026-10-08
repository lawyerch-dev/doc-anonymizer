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
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
# 子路径部署(如 GitHub Pages 项目页)时, 仓库 markdown 的相对链接也要带上同样的前缀
BASE = (os.environ.get("SITE_BASE", "") or "").rstrip("/")
SITE = HERE.parent
REPO = SITE.parent
OUT = SITE / "src" / "content" / "docs"

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
H1 = re.compile(r"^#\s+(.+)$", re.M)
# 仓库文档顶部的语言切换行(中英成对): 站点有 Starlight 自己的切换器, 生成时去掉
SWITCHER = re.compile(r"^\s*(?:\[English\]\([^)]*\.en\.md\)\s*\|\s*中文|English\s*\|\s*\[中文\]\([^)]*\.md\))\s*$", re.M)


def render_velora_index(entry: dict) -> str:
    """把 packages/ui/src/manifest.json 渲染成一页总览: 库里有啥, 一眼看到, 不用翻源码。"""
    data = json.loads((REPO / entry["file"]).read_text(encoding="utf-8"))
    groups = {"ui": ("组件", "ui"), "block": ("区块", "ui/blocks")}
    parts = [
        "这一页由 `packages/ui/src/manifest.json` 生成 —— 也就是共享组件包里**真实存在**的东西",
        "（`cd packages/ui && npm run sync` 重新生成）。用法：",
        "",
        "```tsx",
        'import { Marquee } from "@doc-anonymizer/ui/marquee";',
        'import { HeroGlobe } from "@doc-anonymizer/ui/blocks/hero-globe";',
        'import { Button } from "@doc-anonymizer/ui/primitives/button";',
        "```",
        "",
        "线上目录（每个都有 live demo 与 props）：<https://velora.colorlib.com/components>。",
        "",
    ]
    for kind, (label, path) in groups.items():
        items = [i for i in data["items"] if i["type"] == kind]
        parts += [f"## {label}（{len(items)}）", "", "| 名称 | 说明 | 用法 |", "|---|---|---|"]
        for i in items:
            usage = f'`@doc-anonymizer/ui/{path}/{i["name"]}`' if kind == "block" else f'`@doc-anonymizer/ui/{i["name"]}`'
            desc = (i.get("description") or "").replace("|", "\\|")
            parts.append(f'| [{i["name"]}](https://velora.colorlib.com/components/{i["name"]}) | {desc} | {usage} |')
        parts.append("")
    return "\n".join(parts)


def read_page(
    entry: dict,
    file_to_route: dict[str, str],
    *,
    source: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> str:
    """把仓库里的一篇 markdown 变成站点页面(中英共用一套改写逻辑)。

    译文走同一个函数: 只有"读哪个文件、标题/描述写什么"不同, 链接改写规则完全一致。
    """
    src = REPO / (source or entry["file"])
    if not src.is_file():
        sys.exit(f"错误: 清单里的文件不存在: {source or entry['file']}")
    if entry.get("render") == "velora-index":
        body = render_velora_index(entry)
        return (
            "---\n"
            f"title: {json.dumps(entry['title'], ensure_ascii=False)}\n"
            f"description: {json.dumps(entry.get('description', ''), ensure_ascii=False)}\n"
            "---\n\n" + body + "\n"
        )
    text = FRONTMATTER.sub("", src.read_text(encoding="utf-8"))
    text = SWITCHER.sub("", text).lstrip("\n")
    h1 = H1.search(text)
    text = H1.sub("", text, count=1).lstrip("\n")          # 标题进 frontmatter, 正文别再重复
    title = title or entry.get("title") or (h1.group(1).strip() if h1 else src.stem)

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
        return f"]({BASE}/{route}/{suffix})"

    text = re.sub(r"\]\(([^)\s]+)\)", to_route, text)

    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"description: {json.dumps(description or entry.get('description', ''), ensure_ascii=False)}\n"
        "---\n\n" + text.strip() + "\n"
    )


def _title_of(path: pathlib.Path) -> str:
    text = FRONTMATTER.sub("", path.read_text(encoding="utf-8"))
    h1 = H1.search(text)
    title = h1.group(1).strip() if h1 else path.stem
    return title.removeprefix("Agent Note: ").strip()


def discover_extra() -> list[dict]:
    """树里加了就上站, 不用手工维护清单: 已落地的笔记 / 操作手册 / 各包本地规范。"""
    pages: list[dict] = []
    for note in sorted((REPO / ".agent" / "notes" / "implemented").rglob("*.md")):
        pages.append({
            "group": "notes", "slug": note.stem, "title": _title_of(note),
            "description": "决策与修复记录（为什么这么做、踩过什么坑）",
            "file": note.relative_to(REPO).as_posix(),
        })
    for skill in sorted((REPO / ".agent" / "skills").glob("*/SKILL.md")):
        pages.append({
            "group": "skills", "slug": skill.parent.name, "title": _title_of(skill),
            "description": "操作手册（反复发生的事怎么做）",
            "file": skill.relative_to(REPO).as_posix(),
        })
    for post in sorted((REPO / ".agent" / "postmortem").glob("[0-9][0-9][0-9][0-9]-*.md")):
        pages.append({
            "group": "postmortem", "slug": post.stem, "title": _title_of(post),
            "description": "事故复盘（为什么没兜住、补了什么护栏）",
            "file": post.relative_to(REPO).as_posix(),
        })
    for guide in sorted((REPO / "docs" / "cookbook").glob("*.md")):
        pages.append({
            "group": "cookbook", "slug": guide.stem, "title": _title_of(guide),
            "description": "操作指引（每一步都有验证方式）",
            "file": guide.relative_to(REPO).as_posix(),
        })
    for agents in sorted((REPO / "packages").glob("docanon-*/AGENTS.md")):
        pages.append({
            "group": "packages", "slug": agents.parent.name, "title": agents.parent.name,
            "description": "这个包本地的约束（边界、怎么测、本地坑）",
            "file": agents.relative_to(REPO).as_posix(),
        })
    return pages


def main() -> None:
    mp = SITE / "content-manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    pages = manifest["pages"] + discover_extra()
    file_to_route = {p["file"]: f"{p['group']}/{p['slug']}" for p in pages}

    # 清单给出的英文源也进路由表(指向同一条路由), 译文里的相对链接才能一起改写
    for entry in pages:
        if entry.get("en"):
            file_to_route[entry["en"]] = f"{entry['group']}/{entry['slug']}"

    if OUT.exists():
        for old in OUT.rglob("*.md"):
            old.unlink()
    written = []
    for entry in pages:
        dest = OUT / entry["group"] / f"{entry['slug']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(read_page(entry, file_to_route), encoding="utf-8")
        written.append(dest.relative_to(SITE).as_posix())

        if entry.get("en"):
            en_dest = OUT / "en" / entry["group"] / f"{entry['slug']}.md"
            en_dest.parent.mkdir(parents=True, exist_ok=True)
            en_dest.write_text(
                read_page(
                    entry,
                    file_to_route,
                    source=entry["en"],
                    title=entry.get("en_title", entry.get("title")),
                ),
                encoding="utf-8",
            )
            written.append(en_dest.relative_to(SITE).as_posix())

    # 侧栏也由同一份清单生成: 避免 astro.config 里再抄一遍组与顺序
    groups: dict[str, list[dict[str, object]]] = {}
    for entry in pages:
        item: dict[str, object] = {"label": entry["title"], "slug": f"{entry['group']}/{entry['slug']}"}
        if entry.get("en_title"):                      # 侧栏标签跟着语言切换
            item["translations"] = {"en": entry["en_title"]}
        groups.setdefault(entry["group"], []).append(item)
    label_of = {"start": "开始", "dev": "开发", "agent": "契约细则", "packages": "包",
                "skills": "操作手册", "notes": "决策记录", "cookbook": "操作指引", "postmortem": "事故复盘", "other": "其他"}
    label_en = {"start": "Start", "dev": "Development", "agent": "Contract rules", "packages": "Packages",
                "skills": "Playbooks", "notes": "Decision records", "cookbook": "Guides",
                "postmortem": "Post-mortems", "other": "Other"}
    sidebar = [
        {"label": label_of.get(g, g), "translations": {"en": label_en.get(g, g)}, "items": items}
        for g, items in groups.items()
    ]
    sidebar_ts = SITE / "src" / "sidebar.generated.mjs"
    sidebar_ts.write_text(
        "// 由 scripts/sync-content.py 从 content-manifest.json 生成, 不要手改\n"
        "export default " + json.dumps(sidebar, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    if "--record-hashes" in sys.argv:                  # 重新翻译后刷新基线
        import hashlib

        for entry in manifest["pages"]:
            if entry.get("en"):
                digest = hashlib.sha256((REPO / entry["file"]).read_bytes()).hexdigest()[:16]
                entry["en_hash"] = digest
        mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已记录译文基线哈希(en_hash)")

    print(f"同步 {len(written)} 页(含 {sum(1 for e in pages if e.get('en'))} 页英文) → {OUT.relative_to(SITE)}/")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
