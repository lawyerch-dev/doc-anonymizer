"""包边界: 谁依赖谁, 由目录与 pyproject 机械检查。

五包结构(见 docs/architecture.md):
    docanon-contract          引擎与 app 的唯一共享层(只准标准库)
    docanon-engine-ocr        OCR 引擎
    docanon-engine-ner-onnx   ONNX NER 引擎
    docanon-engine-ner-llm    LLM NER 引擎
    docanon-core              app: 抽取/检测编排、脱敏回写、账本、CLI、Web

规则(方向永远是 **core → 引擎 → 契约**):
1. 契约层只准 import 标准库, 也不许声明任何运行时依赖。
2. 引擎包只准 import 标准库/第三方 + `docanon_contract` + **它自己**; 不许碰 core, 也不许碰别的引擎。
3. app(core) 只许用引擎包的**公开面**(`from docanon_engine_x import Y`), 不许伸手进内部模块
   (`docanon_engine_x.detector`) —— 否则引擎内部重构会漏到 core 里。
4. pyproject 的依赖声明要和上面一致: 依赖归属跟着实现走。
"""
from __future__ import annotations

import ast
import pathlib
import sys
import tomllib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

CONTRACT = "docanon_contract"
CORE = "docanon_core"
ENGINES = {
    "ocr": ("docanon-engine-ocr", "docanon_engine_ocr"),
    "ner-onnx": ("docanon-engine-ner-onnx", "docanon_engine_ner_onnx"),
    "ner-llm": ("docanon-engine-ner-llm", "docanon_engine_ner_llm"),
}
STDLIB = set(sys.stdlib_module_names)


def _root(dist: str, pkg: str) -> pathlib.Path:
    return REPO / "packages" / dist / "src" / pkg


def _files(dist: str, pkg: str) -> list[pathlib.Path]:
    return sorted(_root(dist, pkg).rglob("*.py"))


def _imports(path: pathlib.Path, root: pathlib.Path, pkg: str) -> list[str]:
    """解析文件里的包内 import; 只返回 `docanon*` 命名空间里的模块名, 其余丢弃。"""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    package = ".".join([pkg, *parts]) if parts else pkg
    package = package.rsplit(".", 1)[0] if parts else pkg
    out: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            anchor = package
            for _ in range(node.level - 1):
                anchor = anchor.rsplit(".", 1)[0] if "." in anchor else ""
            if node.module:
                out.append(f"{anchor}.{node.module}" if anchor else node.module)
            else:
                for alias in node.names:
                    out.append(f"{anchor}.{alias.name}" if anchor else alias.name)
        elif isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
    return [m for m in out if m.split(".")[0].startswith("docanon")]


def _norm(name: str) -> str:
    """PEP 503 那套等价关系: 发行名里的 `-`/`_` 不分家, 比较时统一成下划线。"""
    return name.strip().lower().replace("-", "_")


def _declared_deps(dist: str) -> set[str]:
    with (REPO / "packages" / dist / "pyproject.toml").open("rb") as fh:
        deps = tomllib.load(fh)["project"].get("dependencies", [])
    return {_norm(d.split()[0].split(">")[0].split("=")[0].split("[")[0]) for d in deps}


# ---------- 1) 契约层只准标准库 ----------
def test_contract_only_uses_stdlib():
    third_party: list[str] = []
    for path in _files("docanon-contract", CONTRACT):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                third_party += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                third_party.append(node.module.split(".")[0])
    bad = [m for m in third_party if m not in STDLIB and m != "__future__"]
    assert not bad, f"契约层混进了第三方依赖: {bad}"


def test_contract_declares_no_dependencies():
    assert _declared_deps("docanon-contract") == set(), "契约层不许有运行时依赖"


# ---------- 2) 引擎包只认契约 + 自己 ----------
@pytest.mark.parametrize("key", sorted(ENGINES))
def test_engine_only_depends_on_contract(key: str):
    dist, pkg = ENGINES[key]
    bad = []
    for path in _files(dist, pkg):
        for mod in _imports(path, _root(dist, pkg), pkg):
            if mod.split(".")[0] in {CONTRACT, pkg}:
                continue
            bad.append(f"{path.relative_to(REPO)}: {mod}")
    assert not bad, f"{dist} 越界依赖(只许 docanon_contract 与它自己): {bad}"


@pytest.mark.parametrize("key", sorted(ENGINES))
def test_engine_declares_only_contract_as_docanon_dep(key: str):
    dist, _ = ENGINES[key]
    docanon_deps = {d for d in _declared_deps(dist) if d.startswith("docanon")}
    assert docanon_deps == {CONTRACT}, f"{dist} 的 docanon 依赖应只有契约, 实际 {docanon_deps}"


def test_engines_are_exactly_the_three_known_packages():
    """引擎包清单是锁定的: 新增/改名都要显式改这里, 免得边界检查悄悄少查一个。"""
    found = {p.name for p in (REPO / "packages").glob("docanon-engine-*")}
    assert found == {dist for dist, _ in ENGINES.values()}


# ---------- 3) core 只用引擎的公开面 ----------
def test_core_uses_engine_public_surface_only():
    bad = []
    for path in _files("docanon-core", CORE):
        for mod in _imports(path, _root("docanon-core", CORE), CORE):
            if any(mod.startswith(f"{pkg}.") for _, pkg in ENGINES.values()):
                bad.append(f"{path.relative_to(REPO)}: {mod}")
    assert not bad, "core 伸手进了引擎内部模块(只许 `from docanon_engine_x import Y`): " + str(bad)


def test_core_declares_the_engines_and_contract():
    docanon_deps = {d for d in _declared_deps("docanon-core") if d.startswith("docanon")}
    assert docanon_deps == {CONTRACT, *(pkg for _, pkg in ENGINES.values())}, (
        f"core 的 docanon 依赖应为契约 + 三个引擎, 实际 {docanon_deps}"
    )
