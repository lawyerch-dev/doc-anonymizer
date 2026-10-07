"""架构约束: **引擎目录即边界**, 契约层只许认识标准库。

`src/docanon/engines/` 下的任何文件都只许 import `docanon.contract` 与 `docanon.engines.*`。
这条规则由目录机械推出, 不再维护人工文件名单 —— 旧写法只检查写死的 5 个文件, 新加一个引擎
文件就完全不受检查(实测: 往 detectors/ 扔一个 `from .. import config` 的文件, 旧测试照样全绿)。

方向永远是 **app → 引擎 → 契约**; 反过来(引擎 import 回 config/注册表)一出现, 这个目录就不能
再整块搬去别的项目, 所以用 AST 锁死。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "docanon"
ENGINE_DIR = SRC / "engines"
STDLIB = set(sys.stdlib_module_names)

# 期望住在 engines/ 下的模块(相对 engines/)。列出来是为了防"引擎被挪走/忘了搬"导致下面
# 那条 parametrize 变成空集而静默通过。
EXPECTED_ENGINE_MODULES = {
    "ocr.py",
    "ocr_image.py",
    "onnx_ner.py",
    "llm/client.py",
    "llm/ner.py",
}


def _module_of(path: pathlib.Path) -> str:
    parts = list(path.relative_to(SRC).parts)
    return ".".join(parts[:-1] + [pathlib.Path(parts[-1]).stem])


def _intra_package_imports(path: pathlib.Path, package: str) -> list[str]:
    """把相对 import 解析成 `docanon.` 之内的模块名(不含 docanon 前缀)。"""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            anchor = package
            for _ in range(node.level - 1):
                anchor = anchor.rsplit(".", 1)[0] if "." in anchor else ""
            if node.module:
                out.append(f"{anchor}.{node.module}" if anchor else node.module)
            else:
                # `from .. import config` 的每个名字都是一个模块(最容易漏判的写法)
                for alias in node.names:
                    out.append(f"{anchor}.{alias.name}" if anchor else alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "docanon" or alias.name.startswith("docanon."):
                    out.append(alias.name[len("docanon"):].lstrip("."))
    return out


def _violations(path: pathlib.Path, package: str) -> list[str]:
    """引擎文件里越界的包内 import; 允许的只有 contract 与 engines.*。"""
    bad = []
    for mod in _intra_package_imports(path, package):
        if mod in {"contract", "engines"} or mod.startswith("engines."):
            continue
        bad.append(mod)
    return bad


def _engine_files() -> list[pathlib.Path]:
    return sorted(p for p in ENGINE_DIR.rglob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("path", _engine_files(), ids=lambda p: str(p.relative_to(ENGINE_DIR)))
def test_engine_does_not_import_app_internals(path: pathlib.Path):
    package = _module_of(path).rsplit(".", 1)[0]
    bad = _violations(path, package)
    assert not bad, (
        f"{path.relative_to(SRC)} 越界依赖了 {bad}"
        "（engines/ 下只许 import docanon.contract 与 docanon.engines.*）"
    )


def test_engine_directory_holds_the_known_engines():
    found = {str(p.relative_to(ENGINE_DIR)) for p in _engine_files()}
    missing = EXPECTED_ENGINE_MODULES - found
    assert not missing, f"engines/ 下少了 {sorted(missing)}；引擎搬走了就要同步这份清单"


def test_boundary_checker_actually_catches_violations(tmp_path):
    """检查器本身有效: 越界要报(含最容易漏判的 `from .. import X`), 合法写法不许误报。"""
    probe = tmp_path / "probe.py"

    # 旧人工名单漏掉的正是这种"新文件 + 越界 import"
    probe.write_text("from .. import config\n", encoding="utf-8")
    assert _violations(probe, "engines") == ["config"]

    probe.write_text("from ... import resources\n", encoding="utf-8")
    assert _violations(probe, "engines.llm") == ["resources"]

    probe.write_text("import docanon.pipeline\n", encoding="utf-8")
    assert _violations(probe, "engines") == ["pipeline"]

    probe.write_text(
        "from ...contract import Block\nfrom .client import LLMClient\n",
        encoding="utf-8",
    )
    assert _violations(probe, "engines.llm") == []


def test_contract_only_uses_stdlib():
    tree = ast.parse((SRC / "contract.py").read_text(encoding="utf-8"))
    third_party = [
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        for alias in (node.names if isinstance(node, ast.Import) else [])
        if not isinstance(node, ast.ImportFrom)
    ] + [
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and not node.level and node.module
    ]
    assert not [m for m in third_party if m not in STDLIB and m != "__future__"], (
        f"契约层混进了第三方依赖: {third_party}"
    )


def test_entity_map_is_app_supplied_not_engine_default(tmp_path):
    """引擎自带实体词表 = 词表跟着引擎仓库走, 移植时必然漂移; 现在它是必填参数。"""
    from docanon.engines import onnx_ner
    from docanon.engines.onnx_ner import OnnxNERDetector

    assert not hasattr(onnx_ner, "DEFAULT_ENTITY_MAP"), "词表不该住回引擎里"
    with pytest.raises(ValueError, match="映射表"):
        OnnxNERDetector(tmp_path, {})


def test_config_carries_the_default_entity_map():
    from docanon.config import DEFAULT_ONNX_ENTITY_MAP, load_config

    cfg = load_config()
    assert cfg.onnx.entity_map == DEFAULT_ONNX_ENTITY_MAP
    assert set(cfg.onnx.entity_map.values()) >= {"PERSON", "PHONE", "ORG"}


def test_engines_command_reports_unusable_engine(tmp_path, monkeypatch, capsys):
    """`docanon engines` 的价值就在"不许猜": 起不来的引擎要出现在结果里并给出非零码。"""
    from docanon.cli import main
    from docanon.engines.llm.client import LLMClient

    cfg_file = tmp_path / "llm.yaml"
    cfg_file.write_text(
        "strategies: {DEFAULT: placeholder}\ndetectors: {rule: true, llm_ner: true}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(LLMClient, "health", lambda self: False)

    code = main(["engines", "-c", str(cfg_file)])

    printed = capsys.readouterr().out
    assert code == 2
    assert "llm" in printed and "不可用" in printed
    assert "rule" in printed and "可用" in printed


def test_engines_command_lists_capabilities(tmp_path, capsys):
    from docanon.cli import main

    assert main(["engines", "-c", "configs/onnx.yaml"]) == 0
    printed = capsys.readouterr().out
    assert "ocr_image" in printed, "抽取器清单要能证明扩展名登记齐了"
    assert "PERSON" in printed, "引擎能力(实体类型)必须列出来"
