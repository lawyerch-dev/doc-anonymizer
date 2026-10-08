# Web 脱敏配置（分层可编辑口径）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Web 一个分层、可保存、可分享的脱敏配置：从模板/预设起步 → 逐类型设策略 → 自定义敏感词 → 按需开关检测器/换模型 → 内联试跑 → 命名保存到 `var/configs/`。

**Architecture:** 配置与内置 `configs/*.yaml` **同 schema**（复用 `load_config` 与 `Config`）。新增 `server/profiles.py` 负责名字规则/结构校验/归一化/落盘（纯函数 + 文件 IO，可独立测）；`routes.py` 只做 HTTP 胶水。`/api/anonymize` 的 `config` 既能是名字（内置或用户）也能是**内联对象**（改完即试跑）；运行期用 `prepare_detectors` 预检，缺引擎返回 400 + 原因。

**Tech Stack:** Python 3.12（stdlib `re`/`pathlib`/`os`）、PyYAML、http.server；前端零构建原生 JS；pytest。

**Spec:** `docs/specs/2026-10-08-redaction-config-design.md`

## Global Constraints

- 引擎只依赖 `docanon_contract` + 自己；core 只用引擎公开面（`tests/test_architecture.py` 锁死）。
- 布局只有一处真相：`resources.LAYOUT`；配置/模型路径按**资源根**解析（`resources.root()`），与 cwd 无关。
- **少于一层就报错，绝不静默**：没产出脱敏结果的条目必须标成未处理；运行期启用却起不来的引擎返回 400 + 原因。
- 落盘只进 `var/configs/`（`var/` 已 gitignore），原子写；**内置 `configs/*.yaml` 只读**，不许改/删。
- 文档一源一址；改现状文档要同步 `.en` 版并跑 `python3 website/scripts/sync-content.py --record-hashes`。
- 加/删测试后同步根 `AGENTS.md` 的「（N 项，约 M 秒）」计数（`tests/test_docs.py` 锁死）。
- 在本项目**需先经用户同意**才真正 `git commit`（用户规则）；计划里的提交步骤在得到同意后才执行。
- 前端无 JS 单测链：前端任务以 `node --check apps/web/app.js` + 文档站构建 + 手工核对为准。

## Review Focus

- **撞名/路径穿越**：用户配置名与内置同名、或含 `..`/`/` —— 必须拒绝，绝不写到 `configs/` 或越出 `var/configs/`。→ T2/T3。
- **非法结构**（策略值未知、检测器名未知、全关检测器、`model_dirs` 非列表）：保存与内联运行都要 400 且**点名**，不能 500、不能静默。→ T2/T6。
- **运行期切到不可用配置**（缺 ONNX 模型 / LLM 连不上）：400 + 原因，不静默降级。→ T6。
- **半截 yaml**（只写了 `strategies`/缺 `detectors`/缺 `onnx`）：归一化补默认后可用，不崩。→ T3/T5。
- **内置只读**：删除/覆盖 `default.yaml` 等必须被拒。→ T5。

---

### Task 1: `config_from_dict` —— 从内存字典构造 Config

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/config.py:61-97`
- Test: `packages/docanon-core/tests/test_config.py`（新建）

**Interfaces:**
- Produces: `config_from_dict(data: dict) -> Config`（`load_config` 复用它）。

- [ ] **Step 1: 写失败测试**

创建 `packages/docanon-core/tests/test_config.py`：

```python
"""config_from_dict: 不落盘也能从字典构造 Config(Web 内联配置用)。"""
from __future__ import annotations

from docanon_core.config import config_from_dict


def test_config_from_dict_builds_from_plain_data():
    cfg = config_from_dict({
        "strategies": {"PERSON": "redact"},
        "dictionary": ["内部项目代号"],
        "detectors": {"rule": True},
        "onnx": {"model_dirs": ["var/models/onnx/gyr66"]},
        "llm": {"base_url": "http://127.0.0.1:9999/v1", "model": "custom"},
        "legacy_convert": False,
    })
    assert cfg.strategy_for("PERSON") == "redact"
    assert cfg.dictionary == ["内部项目代号"]
    assert cfg.detectors == {"rule": True}
    assert cfg.onnx.model_dirs == ["var/models/onnx/gyr66"]
    assert cfg.llm.base_url == "http://127.0.0.1:9999/v1"
    assert cfg.llm.model == "custom"
    assert cfg.legacy_convert is False


def test_config_from_dict_defaults_legacy_convert_true():
    cfg = config_from_dict({"detectors": {"rule": True}})
    assert cfg.legacy_convert is True
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_config.py -q`
Expected: FAIL（`ImportError: cannot import name 'config_from_dict'`）

- [ ] **Step 3: 实现**

把 `config.py` 的 `load_config` 拆成"读文件"与"构造"两段：

```python
def config_from_dict(data: dict) -> Config:
    """从一份已解析的配置字典构造 Config(Web 内联配置/内存构造都走这里)。"""
    llm_raw = data.get("llm", {}) or {}
    onnx_raw = data.get("onnx", {}) or {}
    return Config(
        strategies=data.get("strategies", {}) or {},
        dictionary=data.get("dictionary", []) or [],
        detectors=data.get("detectors", {}) or {},
        legacy_convert=bool(data.get("legacy_convert", True)),
        llm=LLMConfig(
            base_url=llm_raw.get("base_url", LLMConfig.base_url),
            model=llm_raw.get("model", LLMConfig.model),
            timeout=llm_raw.get("timeout", LLMConfig.timeout),
            chunk_size=llm_raw.get("chunk_size", LLMConfig.chunk_size),
            disable_thinking=llm_raw.get("disable_thinking", True),
        ),
        onnx=OnnxConfig(
            model_dirs=onnx_raw.get("model_dirs") or OnnxConfig().model_dirs,
            entity_map=(
                dict(DEFAULT_ONNX_ENTITY_MAP)
                if "entity_map" not in onnx_raw
                else dict(onnx_raw["entity_map"])
            ),
        ),
        raw=data,
    )


def load_config(path: str | Path | None = None) -> Config:
    """读配置。相对路径按资源根解析; 读不到就报错(两种入口都一样)。"""
    if path is None:
        cfg_path = resources.config_path("default.yaml")
    else:
        cfg_path = resources.resolve(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    data: dict = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return config_from_dict(data)
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_config.py packages/docanon-core/tests/test_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/config.py packages/docanon-core/tests/test_config.py
git commit -m "refactor(config): 抽出 config_from_dict, 供内存构造 Config"
```

---

### Task 2: `profiles.py` —— 名字规则、归一化、结构校验

**Files:**
- Create: `packages/docanon-core/src/docanon_core/server/profiles.py`
- Test: `packages/docanon-core/tests/test_profiles.py`（新建）

**Interfaces:**
- Produces: `ProfileError`、`NAME_RE`、`STRATEGY_VALUES`、`DETECTOR_NAMES`、`EDITABLE_KEYS`、
  `validate_name(name)`、`normalize(data)->dict`、`validate(data)`、`is_builtin(ref)->bool`。

- [ ] **Step 1: 写失败测试**

创建 `packages/docanon-core/tests/test_profiles.py`：

```python
"""Web 用户配置: 名字规则 / 归一化 / 结构校验。"""
from __future__ import annotations

import pytest

from docanon_core.detectors import DETECTORS
from docanon_core.server import profiles


def test_detector_names_do_not_drift_from_registry():
    assert set(profiles.DETECTOR_NAMES) == set(DETECTORS)


@pytest.mark.parametrize("name", ["mine", "my-cfg_1", "A" * 32])
def test_validate_name_accepts_safe_names(name):
    profiles.validate_name(name)  # 不抛即通过


@pytest.mark.parametrize("name", ["../x", "a/b", "a.b", "", "x" * 33, "默认"])
def test_validate_name_rejects_dangerous_names(name):
    with pytest.raises(profiles.ProfileError):
        profiles.validate_name(name)


def test_is_builtin_distinguishes_by_extension():
    assert profiles.is_builtin("onnx.yaml")
    assert not profiles.is_builtin("mine")


def test_normalize_fills_missing_keys_from_default():
    out = profiles.normalize({"strategies": {"PERSON": "redact"}})
    assert out["strategies"] == {"PERSON": "redact"}
    assert set(profiles.EDITABLE_KEYS) <= set(out)
    assert out["detectors"].get("rule") is True  # 来自 default.yaml


def test_validate_rejects_unknown_strategy():
    with pytest.raises(profiles.ProfileError, match="未知策略值"):
        profiles.validate({"strategies": {"PERSON": "shred"}})


def test_validate_rejects_all_detectors_off():
    with pytest.raises(profiles.ProfileError, match="检测器"):
        profiles.validate({"detectors": {"rule": False, "dictionary": False,
                                         "onnx_ner": False, "llm_ner": False}})


def test_validate_rejects_unknown_detector_name():
    with pytest.raises(profiles.ProfileError, match="未知检测器"):
        profiles.validate({"detectors": {"rule": True, "magic": True}})


def test_validate_rejects_bad_model_dirs_type():
    with pytest.raises(profiles.ProfileError, match="model_dirs"):
        profiles.validate({"onnx": {"model_dirs": "not-a-list"}})
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_profiles.py -q`
Expected: FAIL（`ModuleNotFoundError: docanon_core.server.profiles`）

- [ ] **Step 3: 实现**

创建 `packages/docanon-core/src/docanon_core/server/profiles.py`：

```python
"""Web 用户配置: 名字规则 / 归一化 / 结构校验 / 落盘(var/configs)。

与内置 `configs/*.yaml` 同 schema, 复用 `config_from_dict` 构造 Config。
只跟文件与词典打交道, 不碰 HTTP(那是 routes.py 的活)。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .. import resources
from ..config import Config, config_from_dict

# 用户配置名: 无点、无路径分隔符 —— 天然不与内置(带 .yaml)撞名, 也杜绝路径穿越
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
# 与 detectors.DETECTORS 的键一致(test_profiles 会核对, 防漂移)
DETECTOR_NAMES: tuple[str, ...] = ("rule", "dictionary", "onnx_ner", "llm_ner")
STRATEGY_VALUES: tuple[str, ...] = ("redact", "mask", "placeholder", "pseudonym", "remove", "keep")
EDITABLE_KEYS: tuple[str, ...] = ("strategies", "dictionary", "detectors", "onnx", "llm", "legacy_convert")
DEFAULT_REF = "default.yaml"


class ProfileError(ValueError):
    """用户配置非法(名字/结构/内置只读)。"""


def user_dir() -> Path:
    return resources.root() / "var" / "configs"


def is_builtin(ref: str) -> bool:
    return isinstance(ref, str) and ref.endswith(".yaml")


def _builtin_path(ref: str) -> Path:
    if Path(ref).name != ref or not ref.endswith(".yaml"):
        raise ProfileError(f"非法内置配置名: {ref!r}")
    return resources.config_path(ref)


def _user_path(name: str) -> Path:
    validate_name(name)
    return user_dir() / f"{name}.yaml"


def validate_name(name: str) -> None:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ProfileError(f"配置名只能是字母/数字/下划线/连字符, 1-32 位: {name!r}")


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path.name} yaml 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{path.name} 顶层不是映射")
    return data


def _default_data() -> dict:
    default = _read_yaml(_builtin_path(DEFAULT_REF))
    return {k: default.get(k) for k in EDITABLE_KEYS}


def normalize(data: dict) -> dict:
    """补齐缺失键(以 default.yaml 为底): 导入的半截 yaml 也可用, 盘上文件保持自包含。"""
    if not isinstance(data, dict):
        raise ProfileError("配置必须是映射")
    base = _default_data()
    return {k: data.get(k, base[k]) for k in EDITABLE_KEYS}


def validate(data: dict) -> None:
    """结构校验; 不通过抛 ProfileError(点名哪里不对)。不看引擎是否真的能起(那是运行时预检)。"""
    data = normalize(data)
    strategies = data["strategies"]
    if not isinstance(strategies, dict):
        raise ProfileError("strategies 必须是映射")
    bad = sorted(f"{k}={v}" for k, v in strategies.items() if v not in STRATEGY_VALUES)
    if bad:
        raise ProfileError(f"未知策略值: {', '.join(bad)}（可选: {', '.join(STRATEGY_VALUES)}）")
    detectors = data["detectors"]
    if not isinstance(detectors, dict):
        raise ProfileError("detectors 必须是映射")
    unknown = sorted(k for k, v in detectors.items() if v and k not in DETECTOR_NAMES)
    if unknown:
        raise ProfileError(f"未知检测器: {', '.join(unknown)}（已登记: {', '.join(DETECTOR_NAMES)}）")
    if not any(detectors.get(n) for n in DETECTOR_NAMES):
        raise ProfileError("至少要启用一个检测器(全关 = 不产出脱敏结果)")
    if not isinstance(data["dictionary"], list):
        raise ProfileError("dictionary 必须是列表")
    onnx = data["onnx"]
    if not isinstance(onnx, dict) or not isinstance(onnx.get("model_dirs"), list):
        raise ProfileError("onnx.model_dirs 必须是列表")


def build_config(data: dict) -> Config:
    return config_from_dict(normalize(data))
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_profiles.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/server/profiles.py packages/docanon-core/tests/test_profiles.py
git commit -m "feat(web): profiles 模块(名字规则/归一化/结构校验)"
```

---

### Task 3: `profiles.py` —— 列表/读取/保存/删除/导入/导出

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/profiles.py`
- Test: `packages/docanon-core/tests/test_profiles.py`

**Interfaces:**
- Consumes: T2 的 `validate_name`/`normalize`/`validate`/`build_config`。
- Produces: `label_of(path)->str`、`list_profiles(current)->list[dict]`、`load_profile(ref)->dict`、
  `save_profile(name,data)`、`delete_profile(name)`、`import_yaml(filename,text)->str`、
  `export_yaml(ref)->str`、`available_onnx_dirs()->list[str]`。

- [ ] **Step 1: 写失败测试**

追加到 `packages/docanon-core/tests/test_profiles.py`：

```python
import yaml


def _isolate(tmp_path, monkeypatch):
    """把用户配置目录指到 tmp_path, 免得污染真实 var/。"""
    monkeypatch.setattr(profiles, "user_dir", lambda: tmp_path / "var" / "configs")


def test_save_load_delete_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    data = profiles.normalize({"strategies": {"PERSON": "pseudonym"}})

    profiles.save_profile("mine", data)
    assert (tmp_path / "var" / "configs" / "mine.yaml").is_file()

    loaded = profiles.load_profile("mine")
    assert loaded["strategies"]["PERSON"] == "pseudonym"
    assert set(profiles.EDITABLE_KEYS) <= set(loaded)

    profiles.delete_profile("mine")
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile("mine")


def test_save_rejects_dangerous_name(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with pytest.raises(profiles.ProfileError):
        profiles.save_profile("../evil", {"detectors": {"rule": True}})


def test_list_profiles_marks_builtin_and_user(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    profiles.save_profile("mine", profiles.normalize({}))

    rows = {r["name"]: r for r in profiles.list_profiles(current="mine")}
    assert rows["onnx.yaml"]["kind"] == "builtin"
    assert rows["mine"]["kind"] == "user"
    assert rows["mine"]["current"] is True
    assert rows["mine"]["label"]


def test_load_half_yaml_is_normalized(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # 直接手写半截文件, 模拟"用户只写了 strategies 的 yaml"
    d = tmp_path / "var" / "configs"
    d.mkdir(parents=True)
    (d / "half.yaml").write_text("strategies:\n  PERSON: redact\n", encoding="utf-8")

    loaded = profiles.load_profile("half")
    assert loaded["strategies"] == {"PERSON": "redact"}
    assert loaded["detectors"].get("rule") is True


def test_import_and_export_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    text = "strategies:\n  ORG: redact\ndetectors:\n  rule: true\n"
    name = profiles.import_yaml("from-file.yaml", text)
    assert name == "from-file"

    out = profiles.export_yaml("from-file")
    assert "ORG: redact" in out and "rule: true" in out


def test_builtin_cannot_be_deleted(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with pytest.raises(profiles.ProfileError):
        # 同名内置不落用户目录: 删除内置名会因"用户配置不存在"而拒绝
        profiles.delete_profile("default.yaml")


def test_available_onnx_dirs_lists_relative_dirs():
    rows = profiles.available_onnx_dirs()
    assert isinstance(rows, list)
    assert all(d.startswith("var/models/onnx/") for d in rows)
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_profiles.py -q`
Expected: FAIL（`AttributeError: … list_profiles`）

- [ ] **Step 3: 实现**

追加到 `profiles.py`（`save_profile` 用原子写；名字经 `validate_name`）：

```python
def label_of(path: Path) -> str:
    """取首行注释当标签; 没有就用文件名主干。"""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if text:
                return text
        elif line:
            break
    return path.stem


def list_profiles(current: str | None) -> list[dict]:
    out: list[dict] = []
    for f in sorted(resources.path("configs").glob("*.yaml")):
        out.append({"name": f.name, "kind": "builtin",
                    "label": label_of(f), "current": f.name == current})
    user_root = user_dir()
    for f in (sorted(user_root.glob("*.yaml")) if user_root.is_dir() else []):
        out.append({"name": f.stem, "kind": "user",
                    "label": label_of(f) or f.stem, "current": f.stem == current})
    return out


def load_profile(ref: str) -> dict:
    path = _builtin_path(ref) if is_builtin(ref) else _user_path(ref)
    if not path.is_file():
        raise ProfileError(f"配置不存在: {ref}")
    return normalize(_read_yaml(path))


def save_profile(name: str, data: dict) -> None:
    data = normalize(data)
    validate(data)
    path = _user_path(name)  # 顺带校验名字
    user_dir().mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)


def delete_profile(name: str) -> None:
    path = _user_path(name)
    if not path.is_file():
        raise ProfileError(f"用户配置不存在: {name}")
    path.unlink()


def import_yaml(filename: str, text: str) -> str:
    name = Path(filename).stem
    validate_name(name)
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ProfileError("导入的 yaml 顶层不是映射")
    save_profile(name, data)
    return name


def export_yaml(ref: str) -> str:
    return yaml.safe_dump(load_profile(ref), allow_unicode=True, sort_keys=False)


def available_onnx_dirs() -> list[str]:
    """var/models/onnx 下的模型目录(相对资源根, 与 config.onnx.model_dirs 同一坐标系)。"""
    base = resources.path("models") / "onnx"
    if not base.is_dir():
        return []
    root = resources.root()
    return sorted(p.relative_to(root).as_posix() for p in base.iterdir() if p.is_dir())
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_profiles.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/server/profiles.py packages/docanon-core/tests/test_profiles.py
git commit -m "feat(web): profiles 列表/读写/导入导出 + 模型目录枚举"
```

---

### Task 4: 只读接口 —— `/api/configs`、`/api/configs/{ref}`、`/api/models`

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`（`do_GET` + 删旧 `_configs`）
- Test: `packages/docanon-core/tests/test_server.py`

**Interfaces:**
- Consumes: `profiles.list_profiles` / `load_profile` / `available_onnx_dirs`（T3）、`ProfileError`。
- Produces: GET 三接口；`Handler._json_error(code, msg)` 小助手。

- [ ] **Step 1: 写失败测试**

追加到 `packages/docanon-core/tests/test_server.py`：

```python
def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return json.loads(resp.read())


def test_api_configs_returns_kind_and_current(ephemeral_server):
    body = _get(ephemeral_server, "/api/configs")
    rows = {c["name"]: c for c in body["configs"]}
    assert rows["onnx.yaml"]["kind"] == "builtin"
    assert rows["default.yaml"]["current"] is True


def test_api_config_get_returns_editable_data(ephemeral_server):
    body = _get(ephemeral_server, "/api/configs/onnx.yaml")
    assert body["kind"] == "builtin"
    data = body["data"]
    assert data["strategies"]["PERSON"] == "redact"
    assert "model_dirs" in data["onnx"]


def test_api_config_get_unknown_is_404(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/nope.yaml")
    assert excinfo.value.code == 404


def test_api_config_get_traversal_is_rejected(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/..%2fdefault.yaml")
    assert excinfo.value.code in (400, 404)


def test_api_models_lists_onnx_dirs_and_llm_defaults(ephemeral_server):
    body = _get(ephemeral_server, "/api/models")
    assert isinstance(body["onnx_dirs"], list)
    assert body["llm"]["base_url"].startswith("http")
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: FAIL（`/api/configs` 仍返回旧形状；`/api/models` 不存在）

- [ ] **Step 3: 实现**

在 `routes.py` 顶部导入（替换旧导入）：

```python
from .. import convert, resources
from ..config import load_config
from ..pipeline import prepare_detectors, process_file
from ..redaction.mapping import MappingStore
from . import profiles
from docanon_engine_ner_llm import LLMConfig
```

删除类内旧的 `_configs()` 静态方法（行 161-183），改为在 `do_GET` 分派新接口：

```python
        elif p == "/api/configs":
            self._json(200, {"configs": profiles.list_profiles(self.config_name)})
        elif p == "/api/models":
            self._json(200, {
                "onnx_dirs": profiles.available_onnx_dirs(),
                "llm": {"base_url": LLMConfig.base_url, "model": LLMConfig.model},
            })
        elif p.startswith("/api/configs/"):
            self._get_config(p[len("/api/configs/"):])
        elif p in _WEB_ASSETS:
            self._send_file(_web() / _WEB_ASSETS[p])
```

加方法：

```python
    # ---------- 配置只读 ----------
    def _get_config(self, ref: str) -> None:
        if ref.endswith("/export"):
            try:
                text = profiles.export_yaml(ref[: -len("/export")])
            except profiles.ProfileError as exc:
                self._json(404, {"error": str(exc)})
                return
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-yaml; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{Path(ref[:-len("/export")]).stem}.yaml"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            data = profiles.load_profile(ref)
        except profiles.ProfileError as exc:
            code = 404 if "不存在" in str(exc) else 400
            self._json(code, {"error": str(exc)})
            return
        self._json(200, {"ref": ref, "kind": "builtin" if profiles.is_builtin(ref) else "user", "data": data})
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/server/routes.py packages/docanon-core/tests/test_server.py
git commit -m "feat(web): GET /api/configs|/api/models + 单份读取"
```

---

### Task 5: 写入接口 —— PUT 保存 / POST 导入 / DELETE / 导出

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`（新增 `do_PUT`/`do_DELETE`；`do_POST` 加 import）
- Test: `packages/docanon-core/tests/test_server.py`

**Interfaces:**
- Consumes: `profiles.save_profile` / `delete_profile` / `import_yaml`（T3）。
- Produces: PUT `/api/configs/{name}`、DELETE `/api/configs/{name}`、POST `/api/configs/import`；`Handler._read_json()` 抽出复用。

- [ ] **Step 1: 写失败测试**

追加到 `packages/docanon-core/tests/test_server.py`：

```python
def _request(base, path, method, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def test_put_save_then_get_and_delete(tmp_path, ephemeral_server):
    data = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    data["strategies"]["PERSON"] = "pseudonym"

    assert _request(ephemeral_server, "/api/configs/mine", "PUT", data)["saved"] is True
    got = _get(ephemeral_server, "/api/configs/mine")["data"]
    assert got["strategies"]["PERSON"] == "pseudonym"

    _request(ephemeral_server, "/api/configs/mine", "DELETE")
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(ephemeral_server, "/api/configs/mine")
    assert excinfo.value.code == 404


def test_put_rejects_bad_structure(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request(ephemeral_server, "/api/configs/mine", "PUT",
                 {"strategies": {"PERSON": "shred"}})
    assert excinfo.value.code == 400
    assert "未知策略值" in json.loads(excinfo.value.read())["error"]


def test_delete_builtin_is_rejected(ephemeral_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _request(ephemeral_server, "/api/configs/default.yaml", "DELETE")
    assert excinfo.value.code == 400


def test_import_yaml_creates_user_profile(ephemeral_server):
    import base64
    text = "strategies:\n  ORG: redact\ndetectors:\n  rule: true\n"
    body = _post(ephemeral_server, "/api/configs/import", {
        "filename": "imported.yaml",
        "content_b64": base64.b64encode(text.encode()).decode(),
    })
    assert body["name"] == "imported"
    assert _get(ephemeral_server, "/api/configs/imported")["data"]["strategies"]["ORG"] == "redact"
```

另需把 `ephemeral_server` fixture 的 `Handler.out_root` 指向 tmp 后，用户配置目录仍写真实 `var/`——为隔离，
在 fixture 里补一行（见 Step 3 的 conftest 改动）。

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: FAIL（`do_PUT` 不存在 → 501）

- [ ] **Step 3: 实现**

`conftest.py` 的 `ephemeral_server` 里，把用户配置目录也隔离到 tmp：

```python
    from docanon_core import server
    from docanon_core.server import profiles
    from docanon_core.config import load_config

    monkeypatch.setattr(server.Handler, "out_root", tmp_path)
    monkeypatch.setattr(server.Handler, "config", load_config())
    monkeypatch.setattr(server.Handler, "config_name", "default.yaml")
    monkeypatch.setattr(profiles, "user_dir", lambda: tmp_path / "var" / "configs")
```

`routes.py` 抽出读体助手，并在 `do_POST` 分派 import：

```python
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
```

```python
        if p == "/api/upload":
            self._upload(payload)
        elif p == "/api/anonymize":
            self._anonymize(payload)
        elif p == "/api/configs/import":
            self._import_config(payload)
        else:
            self._send(404, b"not found", "text/plain")
```

加 PUT / DELETE：

```python
    # ---------- 配置写入 ----------
    def do_PUT(self) -> None:  # noqa: N802
        p = self._path()
        if not p.startswith("/api/configs/"):
            self._send(404, b"not found", "text/plain")
            return
        try:
            payload = self._read_json()
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"请求解析失败: {exc}"})
            return
        name = p[len("/api/configs/"):]
        try:
            profiles.save_profile(name, payload)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {"saved": True, "name": name})

    def do_DELETE(self) -> None:  # noqa: N802
        p = self._path()
        if not p.startswith("/api/configs/"):
            self._send(404, b"not found", "text/plain")
            return
        ref = p[len("/api/configs/"):]
        try:
            if profiles.is_builtin(ref):
                raise profiles.ProfileError(f"内置配置只读, 不能删除: {ref}")
            profiles.delete_profile(ref)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {"deleted": ref})

    def _import_config(self, payload: dict) -> None:
        try:
            text = base64.b64decode(payload["content_b64"]).decode("utf-8")
            name = profiles.import_yaml(Path(payload["filename"]).name, text)
        except profiles.ProfileError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"导入失败: {exc}"})
            return
        self._json(200, {"name": name})
```

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py packages/docanon-core/tests/test_profiles.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/server/routes.py conftest.py packages/docanon-core/tests/test_server.py
git commit -m "feat(web): PUT/DELETE/import 配置接口"
```

---

### Task 6: `/api/anonymize` 支持内联/命名配置 + 预检

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py`（`_resolve_config` 重写、`_anonymize` 用 `cfg_name` 写 trace）
- Test: `packages/docanon-core/tests/test_server.py`

**Interfaces:**
- Consumes: `profiles.build_config` / `validate` / `load_profile`（T2/T3）、`config_from_dict`（T1）、`prepare_detectors`。
- Produces: `_resolve_config(payload)` 接受 `config` 为 `None`（启动配置）/`str`（名字）/`dict`（内联）。

- [ ] **Step 1: 写失败测试**

追加到 `packages/docanon-core/tests/test_server.py`：

```python
def test_anonymize_with_inline_config_object(ephemeral_server):
    up = _upload_text(ephemeral_server, "张三 13812340000\n")
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["strategies"]["PHONE"] = "redact"  # 内联改口径: 手机也盖成 **

    body = _post(ephemeral_server, "/api/anonymize",
                 {"token": up["token"], "config": inline})

    assert body["trace"]["config"] == "inline"
    assert body["counts"].get("PHONE") == 1


def test_anonymize_inline_bad_strategy_is_400(ephemeral_server):
    up = _upload_text(ephemeral_server)
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["strategies"]["PHONE"] = "shred"

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "config": inline})
    assert excinfo.value.code == 400
    assert "未知策略值" in json.loads(excinfo.value.read())["error"]


def test_anonymize_inline_enabling_unavailable_onnx_is_400(ephemeral_server, monkeypatch):
    up = _upload_text(ephemeral_server)
    inline = _get(ephemeral_server, "/api/configs/default.yaml")["data"]
    inline["detectors"]["onnx_ner"] = True
    inline["onnx"]["model_dirs"] = ["var/models/onnx/__nope__"]
    # 模拟引擎起不来
    monkeypatch.setattr("docanon_core.pipeline.prepare_detectors",
                        lambda cfg: (_ for _ in ()).throw(RuntimeError("缺 ONNX 模型")))

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(ephemeral_server, "/api/anonymize", {"token": up["token"], "config": inline})
    assert excinfo.value.code == 400
    assert "不可用" in json.loads(excinfo.value.read())["error"]
```

- [ ] **Step 2: 运行，确认失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: FAIL（内联对象被当字符串 → 400 或 500；`trace.config` 不是 `inline`）

- [ ] **Step 3: 实现**

重写 `_resolve_config`（替换 T4 之前的字符串版）：

```python
    def _resolve_config(self, payload: dict):
        """解析 config: 缺省=启动配置; 字符串=内置/用户配置名; 字典=内联(改完即试跑)。

        返回 (config, name); 不可用时已发 400 并返回 (None, None)。
        """
        selected = payload.get("config")
        if selected is None:
            return self.config, self.config_name
        try:
            if isinstance(selected, dict):
                profiles.validate(selected)
                cfg = profiles.build_config(selected)
                name = "inline"
            elif isinstance(selected, str):
                cfg = profiles.build_config(profiles.load_profile(selected))
                name = selected
            else:
                raise profiles.ProfileError("config 只能是配置名或配置对象")
            prepare_detectors(cfg)  # 少一层就报错: 缺模型/连不上在这里拦住
        except profiles.ProfileError as exc:
            self._json(400, {"error": f"配置不合法: {exc}"})
            return None, None
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": f"配置不可用: {exc}"})
            return None, None
        return cfg, name
```

说明：内联配置不缓存（每次来自请求）；命名配置也每次构造，但 `build_detectors` 的进程级指纹缓存仍会命中，
不会重复加载 ONNX。`trace.config` 已由 `_anonymize` 写入 `cfg_name`（T4 已就位），此处 `name="inline"` 即可。

- [ ] **Step 4: 运行，确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add packages/docanon-core/src/docanon_core/server/routes.py packages/docanon-core/tests/test_server.py
git commit -m "feat(web): /api/anonymize 支持内联与命名配置 + 预检 400"
```

---

### Task 7: 前端 L1 —— 口径列表 + 内联试跑

**Files:**
- Modify: `apps/web/index.html`（下拉区域）
- Modify: `apps/web/app.js`（`loadConfigs` 重写、`state.configData`、运行带内联对象）

**Interfaces:**
- Consumes: `GET /api/configs`、`GET /api/configs/{ref}`、`POST /api/anonymize` 的 `config` 对象。

- [ ] **Step 1: 实现（前端无 JS 单测链；本步即为实现，第 2 步验证）**

`index.html`：把现有

```html
      <label class="hint" for="cfgSel" style="display:block;margin-top:10px">脱敏口径</label>
      <select id="cfgSel" style="width:100%"></select>
```

改为：

```html
      <label class="hint" for="cfgSel" style="display:block;margin-top:10px">脱敏口径</label>
      <select id="cfgSel" style="width:100%"></select>
      <div id="cfgMeta" class="hint" style="margin-top:4px"></div>
```

`app.js`：`state` 增加 `configData`；用以下实现替换旧的 `loadConfigs`：

```js
async function loadConfigs() {
  const sel = $('cfgSel');
  try {
    const { configs } = await (await fetch('/api/configs', { cache: 'no-store' })).json();
    sel.innerHTML = '';
    configs.forEach(c => {
      const o = document.createElement('option');
      o.value = c.name;
      o.textContent = c.label + (c.kind === 'user' ? '（我的）' : '') + (c.current ? '（当前）' : '');
      sel.appendChild(o);
    });
    const saved = localStorage.getItem('docanon.config');
    const pick = configs.find(c => c.name === saved) || configs.find(c => c.current) || configs[0];
    sel.onchange = () => { localStorage.setItem('docanon.config', sel.value); loadConfigData(sel.value); };
    if (pick) { sel.value = pick.name; await loadConfigData(pick.name); }
  } catch (e) {
    sel.innerHTML = '<option>配置加载失败</option>';
  }
}

async function loadConfigData(ref) {
  try {
    const body = await (await fetch('/api/configs/' + encodeURIComponent(ref), { cache: 'no-store' })).json();
    if (body.error) throw new Error(body.error);
    state.configRef = ref;
    state.configData = body.data;
    $('cfgMeta').textContent = ref + (body.kind === 'user' ? ' · 我的配置' : ' · 内置');
    if (typeof renderEditors === 'function') renderEditors();
  } catch (e) {
    $('cfgMeta').textContent = '读取失败: ' + e.message;
  }
}
```

运行处（`$('run').onclick`）把 body 改成用内联对象：

```js
    const body = state.preset ? { preset: state.preset } : { token: state.token };
    if (state.configData) body.config = state.configData;
```

`state` 定义改为：

```js
const state = { preset: null, token: null, filename: null, url: null, trace: null, logOpen: false, configRef: null, configData: null };
```

- [ ] **Step 2: 验证**

Run: `node --check apps/web/app.js && .venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q`
Expected: `app.js` 语法 OK；server 测试 PASS（后端不受前端影响）

手工：`npm run dev` → 选 `onnx.yaml` → 上传一份 txt → 开始脱敏 → 运行日志出现"口径 onnx.yaml"。

- [ ] **Step 3: Commit（经用户同意后）**

```bash
git add apps/web/index.html apps/web/app.js
git commit -m "feat(web): 口径下拉改为读 /api/configs 并内联试跑"
```

---

### Task 8: 前端 L2/L3 —— 逐类型策略、词典、检测器/模型 + 保存/导入/导出

**Files:**
- Modify: `apps/web/index.html`（L2/L3 折叠区 + 操作按钮）
- Modify: `apps/web/app.js`（`renderEditors` + 保存/导入/导出）

**Interfaces:**
- Consumes: `state.configData`（T7）、`GET /api/models`、`PUT/DELETE /api/configs/{name}`、`POST /api/configs/import`、`GET /api/configs/{ref}/export`。

- [ ] **Step 1: 实现**

`index.html`：在 `#cfgMeta` 之后、`#run` 之前插入：

```html
      <details id="advRedact" style="margin-top:8px">
        <summary>自定义脱敏</summary>
        <label style="display:block;margin:6px 0">
          <input type="checkbox" id="fakeNames"> 用假名替代人名/机构
        </label>
        <table id="stratTable" class="mini-table"></table>
        <label class="hint" for="dictInput">自定义敏感词（逗号分隔）</label>
        <input type="text" id="dictInput" style="width:100%">
      </details>
      <details id="advEngines" style="margin-top:8px">
        <summary>检测引擎</summary>
        <div id="detBox" style="margin:6px 0"></div>
        <label class="hint" for="modelDirs">ONNX 模型目录（可多选）</label>
        <select id="modelDirs" multiple size="3" style="width:100%"></select>
        <label class="hint" for="llmUrl">LLM 地址</label>
        <input type="text" id="llmUrl" style="width:100%">
        <label class="hint" for="llmModel">LLM 模型名</label>
        <input type="text" id="llmModel" style="width:100%">
      </details>
      <div style="display:flex;gap:6px;margin-top:8px">
        <button class="ghost" id="saveCfg" style="flex:1">保存为…</button>
        <button class="ghost" id="importCfg" style="flex:1">导入</button>
        <button class="ghost" id="exportCfg" style="flex:1">导出</button>
      </div>
      <input type="file" id="cfgFile" accept=".yaml,.yml" class="hidden">
```

`app.js` 追加以下实现（放在 `loadConfigs` 附近；`renderEditors` 供 T7 的 `loadConfigData` 调用）：

```js
const ENTITY_TYPES = ['PHONE','ID_CARD','PASSPORT','PLATE','BANK_CARD','EMAIL','IP','USCC',
  'PERSON','ORG','LOCATION','AMOUNT','DOB','SECRET','CUSTOM','DEFAULT'];
const STRATEGIES = ['redact','mask','placeholder','pseudonym','remove','keep'];
const EFFECT = { redact: '**', mask: '138****0000', placeholder: '<PHONE_1>',
  pseudonym: '林芳', remove: '（删除）', keep: '（不动）' };

function renderEditors() {
  const d = state.configData;
  if (!d) return;
  // L2 策略表
  const rows = ENTITY_TYPES.map(t => {
    const cur = (d.strategies || {})[t] || 'redact';
    const opts = STRATEGIES.map(s => '<option value="' + s + '"' + (s === cur ? ' selected' : '') + '>' + s + '</option>').join('');
    return '<tr><td>' + t + '</td><td><select data-entity="' + t + '">' + opts + '</select></td>' +
      '<td class="hint">' + EFFECT[cur] + '</td></tr>';
  }).join('');
  $('stratTable').innerHTML = '<tr><th>类型</th><th>策略</th><th>效果</th></tr>' + rows;
  $('stratTable').querySelectorAll('select[data-entity]').forEach(sel => {
    sel.onchange = () => {
      state.configData.strategies[sel.dataset.entity] = sel.value;
      renderEditors();
    };
  });
  // 假名开关: 依据 PERSON/ORG 是否 pseudonym 反推
  $('fakeNames').checked = d.strategies.PERSON === 'pseudonym' && d.strategies.ORG === 'pseudonym';
  $('fakeNames').onchange = () => {
    const v = $('fakeNames').checked ? 'pseudonym' : 'redact';
    d.strategies.PERSON = v; d.strategies.ORG = v; renderEditors();
  };
  // 词典
  $('dictInput').value = (d.dictionary || []).join('，');
  $('dictInput').onchange = () => {
    state.configData.dictionary = $('dictInput').value.split(/[，,]/).map(s => s.trim()).filter(Boolean);
  };
  // L3 检测器
  $('detBox').innerHTML = ['rule','dictionary','onnx_ner','llm_ner'].map(n =>
    '<label style="display:block"><input type="checkbox" data-det="' + n + '"' +
    (d.detectors[n] ? ' checked' : '') + '> ' + n + '</label>').join('');
  $('detBox').querySelectorAll('input[data-det]').forEach(cb => {
    cb.onchange = () => { state.configData.detectors[cb.dataset.det] = cb.checked; };
  });
  $('llmUrl').value = (d.llm && d.llm.base_url) || '';
  $('llmUrl').onchange = () => { state.configData.llm.base_url = $('llmUrl').value; };
  $('llmModel').value = (d.llm && d.llm.model) || '';
  $('llmModel').onchange = () => { state.configData.llm.model = $('llmModel').value; };
  loadModelDirs();
}

async function loadModelDirs() {
  try {
    const { onnx_dirs } = await (await fetch('/api/models', { cache: 'no-store' })).json();
    const chosen = new Set((state.configData.onnx && state.configData.onnx.model_dirs) || []);
    $('modelDirs').innerHTML = onnx_dirs.map(d =>
      '<option value="' + d + '"' + (chosen.has(d) ? ' selected' : '') + '>' + d + '</option>').join('');
    $('modelDirs').onchange = () => {
      state.configData.onnx.model_dirs = Array.from($('modelDirs').selectedOptions).map(o => o.value);
    };
  } catch (e) { /* 无模型目录时静默留空 */ }
}

async function saveConfig() {
  const name = prompt('配置名（字母/数字/下划线/连字符）:', state.configRef && !state.configRef.endsWith('.yaml') ? state.configRef : 'my-config');
  if (!name) return;
  const r = await fetch('/api/configs/' + encodeURIComponent(name), {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state.configData),
  });
  const body = await r.json();
  if (body.error) { showErr('保存失败: ' + body.error); return; }
  localStorage.setItem('docanon.config', name);
  await loadConfigs();
}

$('saveCfg').onclick = saveConfig;
$('exportCfg').onclick = () => { if (state.configRef) location.href = '/api/configs/' + encodeURIComponent(state.configRef) + '/export'; };
$('importCfg').onclick = () => $('cfgFile').click();
$('cfgFile').onchange = async () => {
  const f = $('cfgFile').files[0]; if (!f) return;
  const buf = new Uint8Array(await f.arrayBuffer());
  let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  const r = await fetch('/api/configs/import', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: f.name, content_b64: btoa(s) }) });
  const body = await r.json();
  if (body.error) { showErr('导入失败: ' + body.error); return; }
  await loadConfigs();
};
```

- [ ] **Step 2: 验证**

Run: `node --check apps/web/app.js`
Expected: 语法 OK

手工（`npm run dev`）逐项核对：
1. 展开「自定义脱敏」，把 `PERSON` 改成 `pseudonym`，再改成 `redact`，效果列随之变化；
2. 勾掉 `dictionary` 检测器 → 开始脱敏 → 运行日志里检测器少了 dictionary；
3. 「保存为…」命名 `mine` → 下拉出现 `mine（我的）`；刷新页面仍在；
4. 「导出」下载 yaml；「导入」该 yaml → 生成同名用户配置；
5. 选一个启用 `onnx_ner` 但模型目录填不存在的配置 → 开始脱敏 → 明确报"配置不可用"（400），不是空白。

- [ ] **Step 3: Commit（经用户同意后）**

```bash
git add apps/web/index.html apps/web/app.js
git commit -m "feat(web): L2/L3 配置编辑器 + 保存/导入/导出"
```

---

### Task 9: 文档同步与决策记录

**Files:**
- Modify: `README.md`、`README.en.md`
- Modify: `.agent/rules/07-frontend.md`
- Modify: `CHANGELOG.md`、`AGENTS.md`（测试计数）
- Create: `.agent/notes/implemented/feature/2026-10-08-web-redaction-config.md`
- Modify: `website/content-manifest.json`（跑脚本刷新 en_hash）
- Test: `tests/test_docs.py`

**Interfaces:**
- Consumes: 前面全部任务。

- [ ] **Step 1: 写决策笔记**

创建 `.agent/notes/implemented/feature/2026-10-08-web-redaction-config.md`：

```markdown
# Agent Note: Web 分层脱敏配置

Status: implemented

## 问题

Web 的"配置"只是选一个 `configs/*.yaml`, 标签取首行注释——用户既表达不了"这个类型要怎么处理",
也调不了模型; 想微调只能去改仓库文件。默认还产可信假名(已被后续收敛为 `**`), 更让人以为没脱敏。

## 决定

- 用户配置 = `var/configs/<name>.yaml`, 与内置同 schema(复用 `load_config`/`Config`); **内置只读**。
- 分层 UI: L1 口径 → L2 逐类型策略 + 词典 → L3 检测器/模型。
- 运行用**内联配置**试跑(改完即测), 满意再命名保存/导出; 运行期用 `prepare_detectors` 预检, 缺引擎返回 400+原因。
- 不暴露 OCR/命名等"静默少一层"或属契约的选项。

## 代价

- 运行期改检测器要加载引擎(ONNX 秒级 / LLM 需 health), 靠 400 明确报错兜住。
- 浏览器"未保存"与已存文件可能不一致, UI 需明示当前是内置/我的/未保存。
```

- [ ] **Step 2: 运行文档守卫，确认失败**

Run: `.venv/bin/python -m pytest tests/test_docs.py -q`
Expected: FAIL（README 未提新接口/笔记未被链接/AGENTS 计数）

- [ ] **Step 3: 同步文档**

- `README.md` Web 章节：补 `GET /api/configs`、`/api/models`、`config` 可传内联对象、`var/configs/` 用户配置、三层说明；
  并把设计文档链进「文档」表（`docs/specs/2026-10-08-redaction-config-design.md`）。
- `README.en.md`：同上英译。
- `.agent/rules/07-frontend.md`：加一节"Web 配置面"（内置/用户配置、分层、预检语义、只读内置）。
- `CHANGELOG.md`：记一条（分层配置、`/api/configs`、用户配置目录）。
- 在 `.agent/rules/07-frontend.md`（或 README）里链到新笔记文件名，满足"笔记必须被链到"。
- 跑 `python3 website/scripts/sync-content.py --record-hashes`。
- 跑全量测试拿到真实项数，更新根 `AGENTS.md` 的「（N 项，约 M 秒）」。

- [ ] **Step 4: 全量校验**

Run: `.venv/bin/python -m pytest -q`（含 `tests/test_docs.py`）+ `npm run test:web`
Expected: PASS

- [ ] **Step 5: Commit（经用户同意后）**

```bash
git add README.md README.en.md .agent/ CHANGELOG.md AGENTS.md website/content-manifest.json docs/specs/2026-10-08-redaction-config-design.md tests/test_docs.py
git commit -m "docs: Web 分层脱敏配置的说明、规则与决策笔记"
```

---

## Self-Review

**Spec coverage:**
- §3 数据模型（同 schema / 引用规则 / 模板与假名开关）→ T1（构造）、T2/T3（名字规则、落盘）、T8（假名开关）。
- §4 接口（configs 列表/读取/写入/删除/导入/导出、models、anonymize 内联）→ T4/T5/T6。
- §5 校验与安全（策略值/检测器名/至少一个/原子写/只读内置/预检）→ T2/T3/T5/T6。
- §6 分层 UI → T7（L1）、T8（L2/L3）。
- §7 运行与预检语义 → T6。
- §8 兼容性（`config` 字符串仍可用）→ T6（`isinstance(str)` 分支）；既有 server 测试保留。
- §9 测试 → T1–T6；前端手工验证 → T7/T8 Step 2。
- §10 文档 → T9。
- §11 风险 → 预检 400（T6）、结构校验点名（T2）、未保存状态（T8 手工项）。

**Placeholder scan:** 无 TBD/TODO；每个代码步骤都给了实际代码。

**Type consistency:** `config_from_dict`（T1）被 `profiles.build_config`（T2）调用；`profiles` 的
`validate_name/normalize/validate/list_profiles/load_profile/save_profile/delete_profile/import_yaml/export_yaml/available_onnx_dirs` 在 T2/T3 定义、T4–T6 消费，命名一致；`_resolve_config` 返回 `(Config, str)`，`trace.config` 用该名字。

**Review Focus:** 每条均有归属任务的测试——撞名/穿越（T2/T3）、非法结构（T2/T6）、运行期不可用（T6）、半截 yaml（T3/T5）、内置只读（T5）。
