"""资源根解析: 猜可以, 猜错不行。

非 editable 安装(pip install 到别处)下旧的 `parents[2]` 会指到 site-packages,
那里没有 configs/ —— 于是 `load_config()` 静默拿到一份空配置, 而空配置在
`docanon engines` 里的样子和"这些引擎我没启用"完全一样。这里锁住"宁可报错"。
"""
from __future__ import annotations

import pathlib

import pytest

from docanon import resources
from docanon.config import load_config


def _fake_root(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs" / "default.yaml").write_text(
        "detectors: {rule: true}\nstrategies: {DEFAULT: placeholder}\n", encoding="utf-8"
    )
    return tmp_path


def test_find_root_from_the_source_tree(repo_root):
    assert resources.find_root(repo_root / "src" / "docanon" / "resources.py") == repo_root


def test_find_root_walks_up_from_a_nested_dir(repo_root):
    """打包/安装后本文件可能躺在更深的子目录里, 逐级向上必须还能找到根。"""
    assert resources.find_root(repo_root / "docs" / "specs") == repo_root


def test_find_root_raises_outside_any_root(tmp_path):
    with pytest.raises(resources.ResourceRootError, match=resources.ENV_ROOT):
        resources.find_root(tmp_path)


def test_env_override_wins(tmp_path, monkeypatch):
    fake = _fake_root(tmp_path)
    monkeypatch.setenv(resources.ENV_ROOT, str(fake))
    assert resources.root() == fake.resolve()
    assert resources.config_path("default.yaml") == fake.resolve() / "configs" / "default.yaml"
    assert resources.web_index() == fake.resolve() / "apps" / "web" / "index.html"
    assert resources.samples_dir() == fake.resolve() / "samples"


def test_default_config_missing_is_an_error(tmp_path, monkeypatch):
    """不带 -c 时默认配置读不到 = 直接报错, 不许退化成空配置。"""
    monkeypatch.setenv(resources.ENV_ROOT, str(tmp_path))
    with pytest.raises(FileNotFoundError, match="default.yaml"):
        load_config()


def test_explicit_config_missing_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv(resources.ENV_ROOT, str(tmp_path))
    with pytest.raises(FileNotFoundError, match="nope.yaml"):
        load_config("nope.yaml")


def test_repo_root_has_the_marked_resources(repo_root):
    """标记文件就是契约: 它不在, 资源根的概念就无从谈起。"""
    assert (repo_root / resources.MARKER).is_file()
