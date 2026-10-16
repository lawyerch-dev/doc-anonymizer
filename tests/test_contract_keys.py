"""数据契约: `Block.locator` / `ExtractedDoc.meta` 的键名只在 `docanon_contract.keys` 里定义。

引擎往元数据里塞键、core 再按这些键读。键名若只在写入方与读取方各自靠约定对齐, 引擎改个名字
core 就**静默失效** —— 而 `test_architecture.py` 用 AST 锁的是 import 方向, 锁不住数据契约。
所以这里把"不许再写裸键名"钉住。

只查**够独特**的键(meta 私有键 + converted_from/out_ext): `format`/`line`/`row` 这类泛用词
会被普通字符串撞上, 不进这份名单(它们仍走 `keys.*`, 只是不做字面量守卫)。
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]

# meta 里那些"只有本仓库会用"的键(独特到不会误伤普通字符串)
DISTINCTIVE = (
    "_scanned_images", "_convert_workdir", "needs_image_redaction",
    "scanned_pages", "converted_from", "out_ext",
)


def _scanned_roots() -> list[pathlib.Path]:
    """读写 locator/meta 的层: 三个引擎包 + core 的 extractors / redaction / pipeline。"""
    roots = list((REPO / "packages").glob("docanon-engine-*/src"))
    core = REPO / "packages" / "docanon-core" / "src" / "docanon_core"
    roots += [core / "extractors", core / "redaction", core / "pipeline.py"]
    return roots


def test_contract_keys_module_exists():
    """键名必须有唯一出处, 且关键的键都在。"""
    path = REPO / "packages" / "docanon-contract" / "src" / "docanon_contract" / "keys.py"
    assert path.is_file(), "少了 docanon_contract/keys.py(键名的唯一出处)"

    from docanon_contract import keys as k

    for name in ("LINE", "PARAGRAPH", "PAGE", "BBOX", "ROW", "COL", "SHEET", "CELL", "SCORE",
                 "FORMAT", "NEEDS_IMAGE", "SCANNED_IMAGES", "SCANNED_PAGES",
                 "CONVERTED_FROM", "OUT_EXT", "CONVERT_WORKDIR"):
        assert hasattr(k, name), f"docanon_contract.keys 少了 {name}"


def test_locator_meta_keys_are_not_written_as_literals():
    """引擎与 core 的抽取/回写层不许再写裸键名 —— 一律从 `docanon_contract.keys` 取。"""
    offenders: list[str] = []
    for root in _scanned_roots():
        paths = [root] if root.is_file() else root.rglob("*.py")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for key in DISTINCTIVE:
                if f'"{key}"' in text or f"'{key}'" in text:
                    offenders.append(f"{path.relative_to(REPO)}: 裸键名 {key!r}")
    assert not offenders, (
        "locator/meta 的键名要从 `docanon_contract.keys` 取, 不许再写裸字符串:\n" + "\n".join(offenders)
    )
