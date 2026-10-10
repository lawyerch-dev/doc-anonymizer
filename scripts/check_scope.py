#!/usr/bin/env python3
"""按改动范围算出"最小但足够"的检查集 —— 不是无脑跑全量, 也不漏掉必须跑的那几条。

为什么需要: 本仓库没有跑测试的 CI(唯一的 CI 只部署文档站), 所以"提交前该跑什么"必须自己判断。
参考 DeepSeek Harness 的做法: 先把**范围**算成事实(改了哪些路径), 再由一张表决定跑什么;
`scripts/change-scope.ts` 只报事实, 策略写在 skill 里, 这里把两件事放在一个脚本里(我们只有一张表)。

只依赖标准库, 所以 setup 之前也能用。

用法:
    python3 scripts/check_scope.py                 # 与自动选出的基线比较
    python3 scripts/check_scope.py --base origin/main
    python3 scripts/check_scope.py --files a b c   # 直接给文件列表(无 git / 测试用)
    python3 scripts/check_scope.py --run           # 顺手把选中的检查按顺序跑掉(遇错即停)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 一张表: 路径前缀 → (这一组是什么, 要跑什么)。顺序无关, 命中即取。
GROUPS: list[tuple[tuple[str, ...], str, list[tuple[str, str]]]] = [
    (
        ("packages/", "tests/", "pyproject.toml", "requirements-dev.txt", "conftest.py", "configs/", "samples/"),
        "Python(五个包 / 测试 / 配置 / 样例)",
        [("npm run test:py", "全量 Python 测试(引擎、产物、账本、还原、文档守卫都在里面)")],
    ),
    (
        ("packages/ui/", "apps/web/", "website/", "package.json", "package-lock.json"),
        "前端(共享组件库 / 产品界面 / 官网文档站 / 工作区)",
        [("npm run test:web", "组件库导入规范化检查 + 文档站构建 + 产品界面类型检查与构建")],
    ),
    (
        ("docs/", ".agent/", ".github/", "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "AGENTS.md"),
        "文档 / 规范 / CI",
        [(".venv/bin/python -m pytest tests/test_docs.py -q", "文档漂移: 路径、链接、数量、单一出处、站点接线、复盘格式")],
    ),
    (
        ("scripts/",),
        "脚本",
        [(".venv/bin/python -m pytest tests/test_dev_env.py -q", "脚本可执行位、字节码缓存、反假绿门禁自身")],
    ),
]

# 这些一改就必须全量(跨层契约或依赖变了, 最小集不足以覆盖)
FORCE_FULL = ("packages/docanon-contract/", "pyproject.toml", "requirements-dev.txt", "conftest.py")

# 没有自动化检查的目录: 要说清楚, 而不是假装覆盖了
MANUAL = {
    "apps/desktop/": "桌面壳: 起 `npm run dev:desktop` 手工验证(需 Rust 工具链)",
}


def picked_base() -> str:
    for candidate in ("origin/main", "main", "master"):
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", candidate], cwd=REPO, capture_output=True).returncode == 0:
            merge = subprocess.run(["git", "merge-base", candidate, "HEAD"], cwd=REPO, capture_output=True, text=True)
            return merge.stdout.strip() or candidate
    return "HEAD~1"


def changed_files(base: str) -> list[str]:
    """committed(相对基线) + 工作区未提交 + 未跟踪 —— 三类都算改动。"""
    cmds = [
        ["git", "diff", "--name-only", base, "HEAD"],
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    seen: list[str] = []
    for cmd in cmds:
        out = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True).stdout
        for line in out.splitlines():
            name = line.strip()
            if name and name not in seen:
                seen.append(name)
    return seen


def classify(files: list[str]) -> tuple[list[list[tuple[str, str]]], list[str], list[tuple[str, str]]]:
    """把改动文件分成: 命中的组(各自要跑的检查) / 无法归类的路径 / 只能手工验证的目录。"""
    hits: list[list[tuple[str, str]]] = []
    for prefixes, _label, checks in GROUPS:
        if any(_matches(f, prefixes) for f in files):
            hits.append(checks)
    unknown = [
        f
        for f in files
        if not any(_matches(f, prefixes) for prefixes, _, _ in GROUPS)
        and not any(f.startswith(p) for p in MANUAL)
    ]
    manual = [(p, advice) for p, advice in MANUAL.items() if any(f.startswith(p) for f in files)]
    return hits, unknown, manual


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    """目录前缀, 或文件名相等(根目录下的 package.json / AGENTS.md 这类)。"""
    return path.startswith(prefixes) or Path(path).name in prefixes


def main() -> int:
    ap = argparse.ArgumentParser(description="按改动范围给出最小检查集")
    ap.add_argument("--base", help="比较的基线 ref(默认自动选 origin/main → main → master → HEAD~1)")
    ap.add_argument("--files", nargs="*", help="直接给改动文件列表(不给就走 git)")
    ap.add_argument("--run", action="store_true", help="把选中的检查按顺序跑掉, 遇错即停")
    args = ap.parse_args()

    base = args.base or picked_base()
    files = args.files if args.files else changed_files(base)
    if not files:
        print("没有改动 —— 不需要跑检查。")
        return 0

    hits, unknown, manual = classify(files)
    print(f"变更范围: {base}..{'工作区' if args.files else 'HEAD'} —— {len(files)} 个文件")
    for f in files[:15]:
        print(f"  {f}")
    if len(files) > 15:
        print(f"  …还有 {len(files) - 15} 个")

    force_full = any(f.startswith(FORCE_FULL) for f in files)
    checks: list[tuple[str, str]] = []
    for group_checks in hits:
        for cmd, why in group_checks:
            if (cmd, why) not in checks:
                checks.append((cmd, why))

    print()
    if force_full or len(hits) > 1 or unknown:
        reason = (
            "改了跨层契约/依赖(契约包、pyproject、requirements、conftest)"
            if force_full
            else ("改动跨了多个组" if len(hits) > 1 else "有无法归类的路径")
        )
        print(f"建议: 全量 `npm test` —— {reason}, 最小集不足以覆盖。")
        checks = [("npm test", "全量: Python + 组件库检查 + 文档站构建")]
    elif hits:
        print("建议(最小集):")
        for cmd, why in checks:
            print(f"  {cmd}\n      {why}")
    else:
        print("建议: 只改了记录类/无关文件 —— 跑 `.venv/bin/python -m pytest tests/test_docs.py -q` 兜一下文档守卫。")
        checks = [(".venv/bin/python -m pytest tests/test_docs.py -q", "文档守卫")]

    if manual:
        print("\n这批改动没有自动化检查, 要手工验证:")
        for prefix, advice in manual:
            print(f"  {prefix} → {advice}")
    if unknown:
        print("\n无法归类的路径(已按最坏情况处理):")
        for f in unknown[:5]:
            print(f"  {f}")

    if not args.run:
        return 0

    print()
    for cmd, _ in checks:
        print(f"$ {cmd}", flush=True)
        proc = subprocess.run(cmd, cwd=REPO, shell=True)
        if proc.returncode != 0:
            print(f"\n✗ 失败(退出码 {proc.returncode}): {cmd}")
            return proc.returncode
    print("\n✓ 最小集全部通过。跨层或发版本时仍建议跑一次 `npm test`。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
