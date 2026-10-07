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
def _markdown_under(*roots: str) -> set[pathlib.Path]:
    found: set[pathlib.Path] = set()
    for root in roots:
        for path in (REPO / root).rglob("*.md"):
            if "node_modules" not in path.parts:
                found.add(path)
    return found


CURRENT_DOCS = sorted(
    {*REPO.glob("*.md"), *_markdown_under("docs", ".github", "apps")} - set(RECORDS)
)
ALL_DOCS = [*CURRENT_DOCS, *RECORDS]

# GitHub 社区标准要求存在的文件(社区档案页会按这几项打分)
COMMUNITY_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
]

TOP_LEVEL = {"packages", "apps", "configs", "samples", "scripts", "tests", "docs", "var"}
# 运行时才存在的东西: var/(权重、预览包、默认产物)、用户自选产物目录、壳的构建产物
RUNTIME_PREFIXES = ("var/", "out/", "apps/docs/out", "apps/desktop/build")

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
            t = token.strip().rstrip("/")
            if not t or any(c in t for c in "*{}…") or " " in t or t.startswith(RUNTIME_PREFIXES):
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


def test_dev_sh_subcommands_are_documented():
    """dev.sh 里能调的每个子命令, 文档里都得有 —— 加了命令忘了写, 这条会红。

    子命令清单以 dev.sh 的 `case "$cmd" in` 分支为准(那是真正会执行的东西)。
    """
    text = (REPO / "scripts" / "dev.sh").read_text(encoding="utf-8")
    dispatch = text.split('case "$cmd" in', 1)[1].split("esac", 1)[0]
    cmds = re.findall(r"^  ([a-z][a-z-]*)\)", dispatch, re.M)
    assert cmds, "没解析出 dev.sh 的子命令(脚本结构变了?)"

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    missing = [c for c in cmds if f"`{c}`" not in readme]
    assert not missing, f"README 里没提这些 dev.sh 子命令: {missing}"


# 同一个主题只允许一个出处: 其余文档用链接指过来。冗余是文档互相矛盾的起点。
SINGLE_OWNER = [
    ("五包目录树", "├── docanon-contract/", "docs/architecture.md"),
    ("已知限制小节", "## 已知限制", "README.md"),
    ("硬边界表", "| 边界 | 锁在哪 |", "docs/architecture.md"),
    ("一键命令清单", "`./scripts/dev.sh help`", "README.md"),
]


def test_each_topic_has_one_owner():
    bad = []
    for what, needle, owner in SINGLE_OWNER:
        if needle not in (REPO / owner).read_text(encoding="utf-8"):
            bad.append(f"{what}: 在 {owner} 里找不到(改名或删了?)")
        for doc in CURRENT_DOCS:
            rel = str(doc.relative_to(REPO))
            if rel != owner and needle in doc.read_text(encoding="utf-8"):
                bad.append(f"{what}: 也出现在 {rel} —— 只该在 {owner}, 其余用链接")
    assert not bad, "\n".join(bad)


def test_docs_site_is_wired_correctly():
    """文档站(apps/docs)接得对不对, 不用跑 npm 也能查一半 —— 另一半靠构建命令。"""
    import re

    site = REPO / "apps" / "docs"
    assert (site / "package.json").is_file(), "apps/docs 不见了"
    pkg = json.loads((site / "package.json").read_text(encoding="utf-8"))
    assert "build" in pkg.get("scripts", {}), "apps/docs 少了 build 脚本"

    cfg = (site / "next.config.ts").read_text(encoding="utf-8")
    assert 'output: "export"' in cfg, "文档站必须静态导出(运行期不发 node)"
    # 这两条与静态导出冲突, 构建会以 "PPR cannot be enabled in export mode" 失败
    # (注释里提到它们没关系, 这里查的是"真的被打开")
    assert "cacheComponents:" not in cfg and "ppr: true" not in cfg, "别打开 cacheComponents/PPR"

    # 侧栏清单指向的 markdown 必须真的存在(否则文档站点进去是 404)
    listing = (site / "src" / "lib" / "docs.ts").read_text(encoding="utf-8")
    files = re.findall(r'file:\s*"([^"]+)"', listing)
    assert len(files) >= 5, f"文档站清单只解析出 {len(files)} 条, 是不是格式变了?"
    missing = [f for f in files if not (REPO / f).is_file()]
    assert not missing, f"文档站清单指向了不存在的文件: {missing}"


def test_markdown_links_resolve():
    bad = []
    for doc in ALL_DOCS:
        for label, target in re.findall(r"\[([^\]]+)\]\(([^)\s#]+)\)", doc.read_text(encoding="utf-8")):
            t = target.strip()
            if not t or t.startswith(("http://", "https://", "mailto:")):
                continue
            if not (doc.parent / t).exists():
                bad.append(f"{doc.relative_to(REPO)}: [{label}]({target})")
    assert not bad, "文档里的相对链接指向了不存在的文件:\n" + "\n".join(bad)


def test_agents_test_count_matches_reality():
    """AGENTS.md 里那句"N 项"必须是真的 —— 它是文档最容易漂移的地方。"""
    claimed = re.search(r"pytest -q`?（(\d+) 项", (REPO / "AGENTS.md").read_text(encoding="utf-8"))
    assert claimed, "AGENTS.md 里找不到「全量测试…（N 项）」那句"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    got = re.search(r"(\d+) tests? collected", proc.stdout)
    assert got, f"收集测试失败:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"

    assert int(claimed.group(1)) == int(got.group(1)), (
        f"AGENTS.md 说 {claimed.group(1)} 项, 实际收集到 {got.group(1)} 项 —— 改了测试就同步那句话"
    )
