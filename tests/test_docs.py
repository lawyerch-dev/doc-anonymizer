"""文档一致性: 不许与代码前后矛盾。

这个仓库最容易犯的错是"代码搬了/改了, 文档还写着旧路径、旧数字"。可机械检查的部分在这里锁住:

1. 文档里点名的仓库路径必须真的存在(排除 glob、以及运行时才生成的 `var/` 与壳的 build);
2. 现状文档里不许再出现已经删掉/改名的名字;
3. `AGENTS.md` 里写的测试数量必须等于实际收集到的数量;
4. 文档里的相对链接必须落地。

带日期的设计文档是**历史记录**(它自己声明"现状以 README/AGENTS/architecture 为准"),
所以只对它做链接检查, 不做"旧名字"检查。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# 记录类文档: 它们本来就要写"当时是什么、后来改成了什么", 所以允许出现旧名字与旧路径。
#   - 设计文档: 带日期的历史记录;
#   - CHANGELOG: 记录"改名前叫什么、迁移前的安装命令是什么"。
RECORDS = [
    REPO / "docs" / "specs" / "2026-10-05-doc-anonymizer-design.md",
    REPO / "CHANGELOG.md",
]

# 现状文档: 扫全部 .md(新写的文档自动纳入检查, 不用来改这份清单)。
# apps/ 下也扫(桌面壳与文档站的 README 同样是现状文档), 但别把 node_modules 里的包文档卷进来。
# 构建产物不是"文档": 同步出来的内容副本、依赖、打包输出都跳过
GENERATED_PARTS = ("node_modules", ".astro", "dist", "out")


def _is_generated(path: pathlib.Path) -> bool:
    rel = path.relative_to(REPO)
    if any(part in GENERATED_PARTS for part in rel.parts):
        return True
    # website/src/content/docs/** 是 sync-content.py 从仓库 markdown 生成的副本
    return rel.parts[:2] == ("website", "src") and "content" in rel.parts


def _markdown_under(*roots: str) -> set[pathlib.Path]:
    return {
        path
        for root in roots
        for path in (REPO / root).rglob("*.md")
        if not _is_generated(path)
    }


# 记录类目录: 写的是"当时是什么样", 允许旧名字与旧路径(与 CHANGELOG/设计历史同待遇)
RECORD_DIRS = (REPO / ".agent" / "notes", REPO / ".agent" / "postmortem")
RECORD_FILES = [p for d in RECORD_DIRS for p in d.rglob("*.md")]

CURRENT_DOCS = sorted(
    {*REPO.glob("*.md"), *_markdown_under("docs", ".github", "apps", ".agent", "packages")}
    - set(RECORDS)
    - set(RECORD_FILES)
)
ALL_DOCS = [*CURRENT_DOCS, *RECORDS, *RECORD_FILES]

# GitHub 社区标准要求存在的文件(社区档案页会按这几项打分)
COMMUNITY_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    ".github/SECURITY.md",
    ".github/CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
]

TOP_LEVEL = {"packages", "apps", "configs", "samples", "scripts", "tests", "docs", "var"}
# 运行时才存在的东西: var/(权重、预览包、默认产物)、用户自选产物目录、壳的构建产物
RUNTIME_PREFIXES = ("var/", "out/", "website/dist", "apps/desktop/build")

# 名字一旦删掉/改名, 现状文档里就不该再有它
REMOVED_NAMES = {
    "src/docanon/": "代码已搬到 packages/",
    "with_llm": "配置已改名 configs/llm.yaml",
    "docanon/engines": "已拆成 packages/docanon-engine-*",
    "pip install -e ": "安装改成 requirements-dev.txt",
    "docanon.contract": "已改名 docanon_contract",
    "docanon.engines": "已拆成 docanon_engine_*",
}


def test_documented_repo_paths_exist():
    """反引号里点名的仓库路径必须是真存在的(否则就是文档在说旧世界)。"""
    missing = []
    for doc in CURRENT_DOCS:  # 记录类文档不查(它们要写旧路径)
        for token in re.findall(r"`([^`\n]+)`", doc.read_text(encoding="utf-8")):
            t = token.strip().rstrip("/").split("::")[0]   # 允许 `file.py::test_name` 这种写法
            if not t or any(c in t for c in "*{}…<>") or " " in t or t.startswith(RUNTIME_PREFIXES):
                continue
            if "/" not in t or t.split("/")[0] not in TOP_LEVEL:
                continue
            if t.startswith((".", "$", "/")):
                continue
            if not (REPO / t).exists():
                missing.append(f"{doc.relative_to(REPO)}: `{token}`")
    assert not missing, "文档点名了不存在的路径:\n" + "\n".join(missing)


def test_current_docs_do_not_use_removed_names():
    bad = []
    for doc in CURRENT_DOCS:
        text = doc.read_text(encoding="utf-8")
        for needle, why in REMOVED_NAMES.items():
            if needle in text:
                bad.append(f"{doc.relative_to(REPO)} 出现 {needle!r} —— {why}")
    assert not bad, "\n".join(bad)


def test_documented_test_file_names_exist():
    """文档里提到的测试文件必须真的存在 —— 允许只写文件名, 但名字要对。"""
    known = {p.name for p in REPO.rglob("test_*.py") if ".venv" not in p.parts}
    bad = []
    for doc in ALL_DOCS:
        for token in set(re.findall(r"\b(test_[a-z_]+\.py)\b", doc.read_text(encoding="utf-8"))):
            if token not in known:
                bad.append(f"{doc.relative_to(REPO)} 提到 {token}, 但仓库里没有这个测试文件")
    assert not bad, "\n".join(bad)


def test_github_community_files_exist():
    """开源项目的门面文件: 少一个, GitHub 的社区档案页就会提示缺项。"""
    missing = [f for f in COMMUNITY_FILES if not (REPO / f).exists()]
    assert not missing, f"缺这些社区标准文件: {missing}"


def test_github_yaml_parses():
    """issue 表单/模板的 YAML 必须能解析 —— 坏一个字符, GitHub 就直接不认这份表单。"""
    import yaml

    bad = []
    for path in sorted((REPO / ".github").rglob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            bad.append(f"{path.relative_to(REPO)}: {exc}")
            continue
        if "body" in (data or {}):  # issue 表单: 字段得有 type, 否则 GitHub 也不认
            for field in data["body"]:
                if not isinstance(field, dict) or "type" not in field:
                    bad.append(f"{path.relative_to(REPO)}: 表单字段缺 type: {field!r}")
    assert not bad, "\n".join(bad)


def test_readme_has_the_product_sections():
    """README 是产品门面: 快速上手、特性、限制、许可这几节不能悄悄消失。"""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for heading in ("## 特性", "## 快速上手", "## 用法", "## 已知限制", "## 文档"):
        assert heading in readme, f"README 里少了「{heading}」这一节"
    assert "[MIT](LICENSE)" in readme, "README 末尾的许可链接没了"


def test_npm_scripts_are_documented():
    """npm scripts 是唯一命令入口 —— 加了脚本却没写进 README, 这条会红。

    脚本清单以根 package.json 为准(那是真正会被执行的东西)。
    """
    pkg = json.loads((REPO / "package.json").read_text(encoding="utf-8"))
    scripts = pkg.get("scripts", {})
    assert scripts, "根 package.json 里没有 scripts"
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    missing = [
        n
        for n in scripts
        if f"npm run {n}" not in readme and f"npm {n}" not in readme and f"`{n}`" not in readme
    ]
    assert not missing, f"README 里没写这些 npm scripts: {missing}"


# 同一个主题只允许一个出处: 其余文档用链接指过来。冗余是文档互相矛盾的起点。
SINGLE_OWNER = [
    ("五包目录树", "├── docanon-contract/", "docs/architecture.md"),
    ("已知限制小节", "## 已知限制", "README.md"),
    ("硬边界表", "| 边界 | 锁在哪 |", "docs/architecture.md"),
    ("npm 命令表", "| `npm run dev:website` | 起官网/文档站", ".agent/rules/01-commands.md"),
]


def _same_document(rel: str, owner: str) -> bool:
    """同一篇文档的另一种语言不算"第二处": 译文承载的是同一个事实。

    例外之外的重复仍然要拦 —— "一个主题只有一个出处"针对的是把同一事实抄进**别的**文档。
    """
    return rel == owner or rel == owner.replace(".md", ".en.md")


def test_each_topic_has_one_owner():
    bad = []
    for what, needle, owner in SINGLE_OWNER:
        if needle not in (REPO / owner).read_text(encoding="utf-8"):
            bad.append(f"{what}: 在 {owner} 里找不到(改名或删了?)")
        for doc in CURRENT_DOCS:
            rel = str(doc.relative_to(REPO))
            if not _same_document(rel, owner) and needle in doc.read_text(encoding="utf-8"):
                bad.append(f"{what}: 也出现在 {rel} —— 只该在 {owner}, 其余用链接")
    assert not bad, "\n".join(bad)


def test_docs_site_is_wired_correctly():
    """官网/文档站(website/ = Astro + Starlight)接得对不对, 不用跑 npm 也能查一半。"""
    site = REPO / "website"
    assert (site / "package.json").is_file(), "website/ 不见了"
    pkg = json.loads((site / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for need in ("astro", "@astrojs/starlight", "@astrojs/react", "@doc-anonymizer/ui"):
        assert need in deps, f"website/ 少了依赖 {need}"
    assert "sync" in pkg.get("scripts", {}), "构建前必须先同步内容(sync)"

    cfg = (site / "astro.config.mjs").read_text(encoding="utf-8")
    assert 'output: "static"' in cfg, "官网必须静态输出(运行期不发 node)"
    assert "sidebar" in cfg, "侧栏应来自生成的清单, 不是在 config 里手写"

    # 内容清单: 指向的仓库文件必须存在, 且同步脚本认得它
    manifest = json.loads((site / "content-manifest.json").read_text(encoding="utf-8"))
    pages = manifest["pages"]
    assert len(pages) >= 8, f"清单只有 {len(pages)} 页, 是不是漏了?"
    missing = [p["file"] for p in pages if not (REPO / p["file"]).is_file()]
    assert not missing, f"官网清单指向了不存在的文件: {missing}"
    slugs = [f"{p['group']}/{p['slug']}" for p in pages]
    assert len(set(slugs)) == len(slugs), f"清单里有重复 slug: {slugs}"
    assert (site / "scripts" / "sync-content.py").is_file(), "少了内容同步脚本"


def test_ui_components_live_only_in_the_shared_package():
    """复用靠共享包: velora 组件只许在 apps/ui, 任何 app 里再放一份就红了。

    这是踩过的坑 —— 第一次集成时把组件拷进了站点 app, 结果产品前端将来根本复用不到。
    """
    kit = REPO / "apps" / "ui"
    assert (kit / "src" / "components" / "velora" / "marquee.tsx").is_file(), "共享组件库 apps/ui 不见了"
    pkg = json.loads((kit / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "@doc-anonymizer/ui"
    exports = pkg.get("exports", {})
    for sub in ("./theme.css", "./manifest.json", "./blocks/*", "./primitives/*", "./*"):
        assert sub in exports, f"共享库少了导出 {sub}"

    # 站点要通过包引用, 而不是自己持有一份组件源码
    site_pkg = json.loads((REPO / "website" / "package.json").read_text(encoding="utf-8"))
    assert "@doc-anonymizer/ui" in site_pkg.get("dependencies", {}), "网站没引共享组件包"

    kit_names = {p.name for p in (kit / "src" / "components" / "velora").glob("*.tsx")}
    strays = [
        str(p.relative_to(REPO))
        for app in (REPO / "website" / "src", REPO / "apps" / "web" / "src")
        for p in app.rglob("*.tsx")
        if "velora" in p.parts or p.name in kit_names
    ]
    assert not strays, f"这些组件不该出现在 app 里(应只放 apps/ui): {strays}"

    root_pkg = json.loads((REPO / "package.json").read_text(encoding="utf-8"))
    assert set(root_pkg.get("workspaces", [])) >= {"apps/ui", "website"}, "根 package.json 的 workspaces 不全"


def test_tailwind_sources_resolve():
    """Tailwind 4 的 @source 必须指向真实目录 —— 指错时类名被静默摇掉(踩过: website 搬家后没改,
    数字组件的 sr-only 失灵、aurora 颜色全丢)。"""
    import re as _re

    css = REPO / "website" / "src" / "styles" / "global.css"
    sources = _re.findall(r'@source\s+"([^"]+)"', css.read_text(encoding="utf-8"))
    assert sources, "global.css 里没有 @source"
    missing = [s for s in sources if not (css.parent / s).resolve().is_dir()]
    assert not missing, f"@source 指向了不存在的目录: {missing}"


def test_ui_kit_ships_the_whole_library():
    """apps/ui 必须是完整组件库(不是我们页面用到的那几个), 且导入已规范化。"""
    kit = REPO / "apps" / "ui"
    manifest = json.loads((kit / "src" / "manifest.json").read_text(encoding="utf-8"))
    items = manifest["items"]
    kinds = {i["type"] for i in items}
    counts = {k: sum(1 for i in items if i["type"] == k) for k in kinds}
    assert counts.get("ui", 0) >= 100, f"velora 组件应 ≥100 个, 实际 {counts.get('ui', 0)}"
    assert counts.get("block", 0) >= 31, f"velora 区块应 ≥31 个, 实际 {counts.get('block', 0)}"

    missing = [i["file"] for i in items if not (kit / i["file"]).is_file()]
    assert not missing, f"清单里的组件文件不存在: {missing[:5]}"

    # 导入必须是相对路径: 消费方不该为 kit 配别名
    leftovers = [
        str(p.relative_to(REPO))
        for p in (kit / "src").rglob("*.ts*")
        if 'from "@/' in p.read_text(encoding="utf-8")
    ]
    assert not leftovers, f"这些文件还在用 shadcn 的 @/ 别名(跑 npm run sync -w @doc-anonymizer/ui): {leftovers[:5]}"


# 借鉴 DeepSeek Harness: 笔记的"状态/分类"编码在路径里, 文件内 Status 必须与目录一致
NOTE_LIFECYCLES = {"proposed", "implemented", "rejected", "archived"}
NOTE_CLASSES = {"feature", "bug-fix", "simplification", "architecture", "process", "testing"}
NOTE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")


def test_notes_follow_the_two_axis_format():
    """每个笔记: 路径 = {状态}/{类别}/日期-主题.md, 且文件内 Status 与目录一致。"""
    root = REPO / ".agent" / "notes"
    notes = [p for p in root.rglob("*.md") if p.name != "README.md"]
    assert notes, "一篇笔记都没有?"
    bad = []
    for note in notes:
        rel = note.relative_to(root)
        parts = rel.parts
        if len(parts) != 3 or parts[0] not in NOTE_LIFECYCLES or parts[1] not in NOTE_CLASSES or not NOTE_NAME.match(parts[2]):
            bad.append(f"{rel}: 路径必须是 {{状态}}/{{类别}}/YYYY-MM-DD-slug.md")
            continue
        text = note.read_text(encoding="utf-8")
        if not text.startswith("# Agent Note: "):
            bad.append(f"{rel}: 首行必须是 '# Agent Note: <标题>'")
        status = re.search(r"^Status: (\S+)", text, re.M)
        if not status:
            bad.append(f"{rel}: 缺 'Status: …' 行")
        else:
            want = "implemented" if parts[0] == "archived" else parts[0]
            if status.group(1) != want:
                bad.append(f"{rel}: Status 是 {status.group(1)}, 与目录 {parts[0]} 不符(应为 {want})")
        if "## 问题" not in text:
            bad.append(f"{rel}: 正文要先讲 '## 问题'(能脱离方案独立成立)")
    assert not bad, "\n".join(bad)


def test_implemented_notes_are_linked_from_real_docs():
    """不做索引文件(DSH 的规则), 但每篇已落地的笔记都要从别处被链到 —— 否则没人会读到它。"""
    notes = sorted((REPO / ".agent" / "notes" / "implemented").rglob("*.md"))
    assert notes, "implemented/ 下没有笔记"
    haystack = "\n".join(
        p.read_text(encoding="utf-8")
        for p in CURRENT_DOCS
        if "notes" not in p.parts or p.parts[:2] != (".agent", "notes")
    )
    orphans = [n.name for n in notes if n.name not in haystack]
    assert not orphans, f"这些笔记没有被任何文档链到(架构表/规则/README 里加一行即可): {orphans}"


def test_skills_declare_when_to_use_them():
    """SKILL.md 必须自描述: frontmatter 的 name 与目录同名, description 以 'Use when ' 开头。"""
    skills = sorted((REPO / ".agent" / "skills").glob("*/SKILL.md"))
    assert skills, "少了 .agent/skills/"
    bad = []
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            bad.append(f"{skill.parent.name}: 缺 frontmatter")
            continue
        if f"name: {skill.parent.name}" not in text:
            bad.append(f"{skill.parent.name}: frontmatter 里的 name 必须与目录同名")
        if not re.search(r"^description: Use when ", text, re.M):
            bad.append(f"{skill.parent.name}: description 要以 'Use when ' 开头(告诉 agent 何时用)")
    assert not bad, "\n".join(bad)


def test_every_package_documents_itself():
    """每个包都有自己的 AGENTS.md(harness 按目录加载), 且被规则索引到。"""
    packages = sorted(p for p in (REPO / "packages").glob("docanon-*") if p.is_dir())
    assert len(packages) >= 5, f"包数量不对: {[p.name for p in packages]}"
    missing = [p.name for p in packages if not (p / "AGENTS.md").is_file()]
    assert not missing, f"这些包少了本地 AGENTS.md: {missing}"
    rules = (REPO / ".agent" / "rules" / "02-packages.md").read_text(encoding="utf-8")
    assert "packages/*/AGENTS.md" in rules, "rules/02-packages.md 里没有索引各包的 AGENTS.md"


def test_website_internal_links_go_through_base():
    """手写 `href="/…"` 在子路径部署(GitHub Pages 项目页)会 404 —— 必须走 website/src/lib/site.ts 的 url()。"""
    offenders = []
    for path in [*(REPO / "website" / "src").rglob("*.astro"), *(REPO / "website" / "src").rglob("*.tsx")]:
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if 'href="/' in line:
                offenders.append(f"{path.relative_to(REPO)}:{num}")
    assert not offenders, f'站内链接要写成 href={{url("/…")}}: {offenders}'


def test_deploy_workflow_matches_the_published_site():
    """唯一的 CI 是"部署文档站": 必须真跑门禁、用 SITE_BASE/SITE_URL 构建、发布 website/dist。"""
    workflow = REPO / ".github" / "workflows" / "deploy-website.yml"
    assert workflow.is_file(), "少了部署 workflow"
    text = workflow.read_text(encoding="utf-8")
    for needle in ("SITE_BASE", "SITE_URL", "website/dist", "npm ci", "npm run test:web", "actions/deploy-pages"):
        assert needle in text, f"部署 workflow 里少了 {needle}"
    config = (REPO / "website" / "astro.config.mjs").read_text(encoding="utf-8")
    assert "SITE_BASE" in config and "SITE_URL" in config, "astro.config.mjs 没用上 SITE_BASE/SITE_URL"


POSTMORTEM_NAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")


def test_postmortems_follow_the_format():
    """复盘必须是 NNNN-slug.md、首行编号一致、先给「执行摘要」、含「根因」与「护栏」, 并被 README 索引。"""
    root = REPO / ".agent" / "postmortem"
    posts = sorted(p for p in root.glob("*.md") if p.name != "README.md")
    assert posts, "一篇事故复盘都没有?"
    index = (root / "README.md").read_text(encoding="utf-8")
    bad = []
    numbers = []
    for post in posts:
        match = POSTMORTEM_NAME.match(post.name)
        if not match:
            bad.append(f"{post.name}: 文件名必须是 NNNN-slug.md")
            continue
        numbers.append(match.group(1))
        text = post.read_text(encoding="utf-8")
        if not text.startswith(f"# 事故复盘 {match.group(1)}："):
            bad.append(f"{post.name}: 首行必须是 '# 事故复盘 {match.group(1)}：<标题>'")
        for section in ("## 执行摘要", "## 根因", "## 护栏"):
            if section not in text:
                bad.append(f"{post.name}: 缺 {section}")
        if "## 影响" in text and text.index("## 执行摘要") > text.index("## 影响"):
            bad.append(f"{post.name}: 「执行摘要」必须排在「影响」之前")
        if post.name not in index:
            bad.append(f"{post.name}: 没有被 .agent/postmortem/README.md 索引到")
    if len(set(numbers)) != len(numbers):
        bad.append(f"编号重复: {numbers}")
    assert not bad, "\n".join(bad)


# 产品层文档必须有英文版(开发内部文档不在其列, 英文站用中文内容回退)
BILINGUAL_REQUIRED = ("README.md", "docs/quickstart.md", "docs/architecture.md", "CONTRIBUTING.md")


def test_bilingual_pages_are_paired_and_fresh():
    """中英必须成对且同步: 英文版存在、能互相切回、且译文基线哈希与中文源一致。

    最后一条是关键 —— 改了中文却忘了改英文, 这里会红(提醒刷新 `--record-hashes`)。
    见 docs/cookbook/maintaining-bilingual-docs.md。
    """
    import hashlib

    manifest = json.loads((REPO / "website" / "content-manifest.json").read_text(encoding="utf-8"))
    paired = {p["file"]: p for p in manifest["pages"] if p.get("en")}
    problems = []

    for required in BILINGUAL_REQUIRED:
        if required not in paired:
            problems.append(f"{required}: 这类文档必须有英文版, 但清单里没登记 en")

    for zh_rel, entry in paired.items():
        zh, en = REPO / zh_rel, REPO / entry["en"]
        if not en.is_file():
            problems.append(f"{zh_rel}: 英文版 {entry['en']} 不存在")
            continue
        if not entry.get("en_title"):
            problems.append(f"{zh_rel}: 缺 en_title(侧栏切换语言时要用)")
        if not entry.get("en_hash"):
            problems.append(f"{zh_rel}: 缺 en_hash(跑 sync-content.py --record-hashes)")
        else:
            digest = hashlib.sha256(zh.read_bytes()).hexdigest()[:16]
            if digest != entry["en_hash"]:
                problems.append(
                    f"{zh_rel}: 中文源改过了但英文版没跟着更新"
                    f" —— 更新 {entry['en']} 后跑 `python3 website/scripts/sync-content.py --record-hashes`"
                )
        if en.name not in zh.read_text(encoding="utf-8"):
            problems.append(f"{zh_rel}: 中文版里没有指向 {en.name} 的切换入口")
        if zh.name not in en.read_text(encoding="utf-8"):
            problems.append(f"{entry['en']}: 英文版里没有指回 {zh.name} 的切换入口")

    assert not problems, "\n".join(problems)


FENCED = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def _link_targets(text: str):
    """取真正的 markdown 链接目标 —— 跳过围栏代码块与行内代码里的示例写法。

    文档里经常要演示链接语法(例如"写成 `[English](x.en.md)`"), 那不是链接, 不该被当成链接查。
    """
    text = FENCED.sub("", text)
    text = INLINE_CODE.sub("", text)
    return re.findall(r"\[([^\]]+)\]\(([^)\s#]+)\)", text)


def test_markdown_links_resolve():
    bad = []
    for doc in ALL_DOCS:
        for label, target in _link_targets(doc.read_text(encoding="utf-8")):
            t = target.strip()
            if not t or t.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc.parent / t).exists():
                bad.append(f"{doc.relative_to(REPO)}: [{label}]({target})")
    assert not bad, "文档里的相对链接指向了不存在的文件:\n" + "\n".join(bad)


def test_agents_test_count_matches_reality():
    """AGENTS.md 里那句"N 项"必须是真的 —— 它是文档最容易漂移的地方。"""
    claimed = re.search(r"（(\d+) 项，约 \d+ 秒", (REPO / "AGENTS.md").read_text(encoding="utf-8"))
    assert claimed, "AGENTS.md 里找不到「（N 项，约 M 秒）」那句"

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}   # 别在仓库里留下字节码
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    got = re.search(r"(\d+) tests? collected", proc.stdout)
    assert got and proc.returncode == 0, (
        f"收集测试失败(需要装齐五个包的环境):\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    )

    assert int(claimed.group(1)) == int(got.group(1)), (
        f"AGENTS.md 说 {claimed.group(1)} 项, 实际收集到 {got.group(1)} 项 —— 改了测试就同步那句话"
    )


AGENTS_MAX_LINES = 80
RULE_MAX_LINES = 60


def test_agent_rules_stay_small_and_indexed():
    """规范按主题拆开才有人读: AGENTS.md 只做索引, 细则在 .agent/rules/, 两边都不许膨胀。"""
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    lines = len(agents.splitlines())
    assert lines <= AGENTS_MAX_LINES, (
        f"AGENTS.md 有 {lines} 行(上限 {AGENTS_MAX_LINES}) —— 细则请拆进 .agent/rules/"
    )

    rule_files = sorted((REPO / ".agent" / "rules").glob("*.md"))
    assert rule_files, "少了 .agent/rules/"
    bad = []
    for rule in rule_files:
        count = len(rule.read_text(encoding="utf-8").splitlines())
        if count > RULE_MAX_LINES:
            bad.append(f"{rule.name} {count} 行(上限 {RULE_MAX_LINES})")
        if rule.name not in agents:
            bad.append(f"{rule.name} 没有被 AGENTS.md 索引到")
    assert not bad, "\n".join(bad)
