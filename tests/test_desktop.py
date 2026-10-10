"""桌面壳的跨语言一致性: 版本号只有一处真相, 打包契约只有一份实现。

这里的每一条都是"换壳/发版时会被静默丢掉"的东西 —— 丢了不会让任何 Python 测试变红,
只会让**发出去的包**装起来有问题(版本号显示不对、资源根没进包、侧车名字对不上)。
所以用守卫钉住, 而不是靠记性。
"""
from __future__ import annotations

import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
DESKTOP = REPO / "apps" / "desktop"
SRC_TAURI = DESKTOP / "src-tauri"


def _group(pattern: str, text: str, what: str) -> str:
    match = re.search(pattern, text, re.M)
    assert match, f"读不出{what}"
    return match.group(1)


def test_version_has_exactly_one_truth():
    """产品版本号在四处出现, 但只能有一个值: pyproject 是真相, 其余三处必须跟着它。

    界面从 /health 读 `docanon_core.__version__`; 安装包的版本号由 Tauri 从 `tauri.conf.json` 取
    (Cargo.toml 的 `[package].version` 只作记录)。三处任一漂移, 用户就会看到
    "访达显示 0.2.0、界面写着 v0.3.0"这种自相矛盾的东西。
    """
    pyproject = (REPO / "packages" / "docanon-core" / "pyproject.toml").read_text(encoding="utf-8")
    truth = _group(r'^version = "([^"]+)"', pyproject, "pyproject 的版本号")

    init = (REPO / "packages" / "docanon-core" / "src" / "docanon_core" / "__init__.py").read_text(encoding="utf-8")
    cargo = (SRC_TAURI / "Cargo.toml").read_text(encoding="utf-8")
    conf = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))

    got = {
        "docanon_core/__init__.py": _group(r'^__version__ = "([^"]+)"', init, "__version__"),
        "apps/desktop/src-tauri/Cargo.toml": _group(r'^version = "(\d[^"]*)"', cargo, "Cargo.toml 的版本号"),
        "apps/desktop/src-tauri/tauri.conf.json": conf["version"],
    }
    wrong = {k: v for k, v in got.items() if v != truth}
    assert not wrong, f"版本号对不上 pyproject 的 {truth}: {wrong} —— 四处必须同步改"


def test_bundle_resource_contract_matches_the_shell():
    """资源根进包的路径三方必须一致: 打进哪个名字、壳按哪个名字去找、dev.sh 摆到哪。

    任何一方改名都是"构建能过、装上才发现界面空白"。壳那侧的标记常量是
    `src-tauri/src/paths.rs` 的 `PACKAGED_MARKER`(= `<PACKAGED_DIR>/configs/default.yaml`)。
    """
    dist_conf = json.loads((SRC_TAURI / "tauri.dist.conf.json").read_text(encoding="utf-8"))
    resources = dist_conf["bundle"]["resources"]
    assert list(resources) == ["../stage/docanon"], f"资源源路径变了: {resources}"
    assert list(resources.values()) == ["docanon"], f"包内目录名变了: {resources}"

    paths_rs = (SRC_TAURI / "src" / "paths.rs").read_text(encoding="utf-8")
    packaged_dir = _group(r'const PACKAGED_DIR: &str = "([^"]+)"', paths_rs, "PACKAGED_DIR")
    assert packaged_dir == "docanon", f"壳找的目录名({packaged_dir})与打包目标名不一致"

    # 资源根只在打包时存在, 所以打包配置必须是**单独一份**; 混进主配置会让日常 tauri dev
    # 直接因"资源路径不存在"起不来
    main_conf = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    assert "resources" not in main_conf.get("bundle", {}), "资源映射不该放在主配置里(dev 起不来)"

    dev_sh = (REPO / "scripts" / "dev.sh").read_text(encoding="utf-8")
    assert "apps/desktop/stage/docanon" in dev_sh, "dev.sh dist 没把资源摆到 stage/docanon"
    assert "tauri.dist.conf.json" in dev_sh, "dev.sh dist 没用上打包专用的那份配置"


def test_sidecar_name_matches_what_the_shell_looks_for():
    """侧车的产物名三方一致: PyInstaller 打什么、壳找什么、CI 冒烟测试跑什么。

    对不上时的症状最难受: 壳会静默退到系统 `python3`(报一堆 ModuleNotFoundError), 或者
    CI 报"没找到包内 sidecar" —— 两种都不像"名字写错了"。
    """
    spec = (DESKTOP / "sidecar" / "docanon-server.spec").read_text(encoding="utf-8")
    name = _group(r'name="([^"]+)",\s*\n\s*debug=False', spec, "spec 里的可执行文件名")
    assert name == "docanon-server", f"spec 的产物名是 {name}"

    backend_rs = (SRC_TAURI / "src" / "backend.rs").read_text(encoding="utf-8")
    paths_rs = (SRC_TAURI / "src" / "paths.rs").read_text(encoding="utf-8")
    assert f'"{name}"' in paths_rs and f'"{name}.exe"' in paths_rs, "壳没按 sidecar/ 下的这个名字去找(含 Windows 的 .exe)"

    workflow = (REPO / ".github" / "workflows" / "build-desktop.yml").read_text(encoding="utf-8")
    assert f"sidecar/{name}/{name}" in workflow, "CI 冒烟测试指向的侧车路径不对"


def test_packaging_inputs_are_committed():
    """图标是打包输入而不是运行期资产: 缺了就没法用别的机器重新打(生成要 rsvg-convert)。

    Windows 的 .ico 与 macOS 的 .icns 都得在 —— Tauri 打哪个平台的包就取哪一份。
    """
    icons = SRC_TAURI / "icons"
    missing = [f for f in ("icon.icns", "icon.ico", "32x32.png", "128x128.png", "128x128@2x.png") if not (icons / f).is_file()]
    assert not missing, f"src-tauri/icons 缺这些(跑 scripts/make_app_icon.sh): {missing}"

    conf = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
    listed = conf["bundle"]["icon"]
    absent = [p for p in listed if not (SRC_TAURI / p).is_file()]
    assert not absent, f"tauri.conf.json 里列的图标不存在: {absent}"

    assert (DESKTOP / "icon.iconset").is_dir(), "缺 icon.iconset(图标源, 生成 icons/ 要它)"
    assert (DESKTOP / "icon.svg").is_file(), "缺 icon.svg(图标的唯一手工源)"
