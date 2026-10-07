"""`scripts/check_scope.py` 是"提交前该跑什么"的唯一出处, 它自己也要被测。

借鉴 DeepSeek Harness 的做法: **把门禁本身当代码测**(它的 `scripts/ci-workflow.spec.ts` 就是干这个)。
这里用 `--files` 绕过 git, 断言几种典型改动的建议。
"""
from __future__ import annotations

import subprocess
import sys

SCOPE = "scripts/check_scope.py"


def _scope(repo_root, *files: str) -> str:
    proc = subprocess.run(
        [sys.executable, SCOPE, "--files", *files],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_python_change_picks_python_suite(repo_root):
    out = _scope(repo_root, "packages/docanon-core/src/docanon_core/pipeline.py")
    assert "npm run test:py" in out
    assert "npm test" not in out.replace("npm run test:py", "")


def test_frontend_change_picks_web_checks(repo_root):
    out = _scope(repo_root, "website/src/pages/index.astro")
    assert "npm run test:web" in out


def test_docs_change_picks_doc_guards(repo_root):
    out = _scope(repo_root, "docs/quickstart.md")
    assert "pytest tests/test_docs.py" in out


def test_contract_change_forces_full_suite(repo_root):
    out = _scope(repo_root, "packages/docanon-contract/src/docanon_contract/engine.py")
    assert "全量 `npm test`" in out


def test_unknown_path_falls_back_to_full_suite(repo_root):
    """不认识的路径按最坏情况处理 —— 宁可多跑, 不能漏跑。"""
    out = _scope(repo_root, "brand-new-dir/thing.txt")
    assert "全量 `npm test`" in out
    assert "无法归类" in out


def test_cross_group_change_forces_full_suite(repo_root):
    out = _scope(repo_root, "docs/quickstart.md", "website/src/pages/index.astro")
    assert "全量 `npm test`" in out


def test_manual_only_area_is_called_out(repo_root):
    """app/desktop 没有自动化检查, 必须明说, 不能假装覆盖了。"""
    out = _scope(repo_root, "apps/desktop/src/index.ts")
    assert "手工验证" in out
