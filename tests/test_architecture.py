"""架构约束: 引擎只许认识契约层, 契约层只许认识标准库。

这两条是"以后能把 OCR / 本地模型引擎搬去别的项目"的前提。方向一旦退化
(引擎 import 回 app 的 config/注册表), 复制目录就不再可行, 所以用 AST 锁死。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "docanon"
STDLIB = set(sys.stdlib_module_names)

# 引擎文件 -> 除了 contract 之外还允许 import 的自己人(子包名)
ENGINES: dict[str, tuple[str, ...]] = {
    "extractors/_ocr.py": ("extractors",),
    "extractors/ocr_image.py": ("extractors",),
    "detectors/onnx_ner.py": (),
    "detectors/llm_ner.py": ("llm",),  # 检测器 + 它的传输层算同一个引擎
    "llm/client.py": ("llm",),
}

# app 侧模块: 引擎一个都不许碰(注册表/配置/编排都在这一侧)
APP_OWNED = {
    "base", "cli", "config", "engines", "mapping", "pipeline", "resolve",
    "resources", "server", "strategies", "writers",
}


def _module_of(path: pathlib.Path) -> str:
    parts = list(path.relative_to(SRC).parts)
    return ".".join(parts[:-1] + [pathlib.Path(parts[-1]).stem])


def _intra_package_imports(path: pathlib.Path) -> list[str]:
    """把相对 import 解析成包内绝对模块名。"""
    out = []
    node_pkg = _module_of(path).rsplit(".", 1)[0]  # 所属包
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            anchor = node_pkg
            for _ in range(node.level - 1):
                anchor = anchor.rsplit(".", 1)[0] if "." in anchor else ""
            mod = f"{anchor}.{node.module}" if anchor and node.module else (anchor or node.module)
            out.append(mod or "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("docanon"):
                    out.append(alias.name)
    return out


@pytest.mark.parametrize("rel", sorted(ENGINES))
def test_engine_does_not_import_app_internals(rel: str):
    for mod in _intra_package_imports(SRC / rel):
        if mod == "contract":
            continue
        top = mod.split(".")[0]
        leaf = mod.rsplit(".", 1)[-1]
        assert top in ENGINES[rel], f"{rel} 越界依赖了 {mod}（引擎只许依赖 docanon.contract）"
        assert leaf not in APP_OWNED, f"{rel} 不该 import app 侧的 {mod}"


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
    from docanon.detectors import onnx_ner
    from docanon.detectors.onnx_ner import OnnxNERDetector

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
    from docanon.llm.client import LLMClient

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
