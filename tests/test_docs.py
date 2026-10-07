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

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

CURRENT_DOCS = [
    REPO / "README.md",
    REPO / "AGENTS.md",
    REPO / "docs" / "architecture.md",
    REPO / "docs" / "benchmarks.md",
    REPO / "scripts" / "README.md",
    REPO / "apps" / "desktop" / "README.md",
]
HISTORICAL = REPO / "docs" / "specs" / "2026-10-05-doc-anonymizer-design.md"
ALL_DOCS = [*CURRENT_DOCS, HISTORICAL]

TOP_LEVEL = {"packages", "apps", "configs", "samples", "scripts", "tests", "docs", "var"}
# 运行时才存在的东西: var/(权重、预览包、默认产物)、用户自选产物目录、壳的构建产物
RUNTIME_PREFIXES = ("var/", "out/", "apps/desktop/build")

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
    for doc in ALL_DOCS:
        for token in re.findall(r"`([^`\n]+)`", doc.read_text(encoding="utf-8")):
            t = token.strip().rstrip("/")
            if not t or any(c in t for c in "*{}") or " " in t or t.startswith(RUNTIME_PREFIXES):
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
