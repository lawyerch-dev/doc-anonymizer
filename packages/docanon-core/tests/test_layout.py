"""布局契约: 仓库/打包根下的路径只有 resources.LAYOUT 一处真相。

存在的意义: 布局知识原本散在 resources 的 4 个函数、config.py 的默认模型路径、server.py 的
URL 前缀、.gitignore 和文档里 —— 挪一个目录不会有任何红灯, 只会在运行时以别的方式炸。
现在改 LAYOUT 一处, 这里有测试立刻对不上。
"""
from __future__ import annotations

import pathlib

from docanon_core import resources


def test_required_layout_is_present_in_this_checkout():
    """源码树必须资源齐全 —— 打包契约的第一步(editable 安装 / bundle 根都以此为准)。"""
    assert resources.missing() == [], f"缺必需资源: {resources.missing()}"
    assert resources.web_index().is_file(), "前端页面必须在 REQUIRED 覆盖的 web 目录里"


def test_accessors_go_through_the_layout_table():
    """访问器不许再自己拼路径, 否则改 LAYOUT 就有漏网的。"""
    assert resources.web_index() == resources.path("web") / "index.html"
    assert resources.vendor_dir() == resources.path("vendor")
    assert resources.samples_dir() == resources.path("samples")
    assert resources.libreoffice_dir() == resources.path("libreoffice")
    assert resources.config_path("default.yaml") == resources.path("configs") / "default.yaml"


def test_layout_entries_are_relative_and_traversal_free():
    for key, rel in resources.LAYOUT.items():
        p = pathlib.PurePosixPath(rel)
        assert not p.is_absolute(), f"{key} 必须是相对资源根的路径: {rel}"
        assert ".." not in p.parts, f"{key} 不许跳出资源根: {rel}"


def test_required_keys_exist_in_layout():
    assert set(resources.REQUIRED) <= set(resources.LAYOUT)


def test_missing_reports_every_gap_at_once(tmp_path, monkeypatch):
    """缺资源时要一次列全(而不是让人把服务起起来才发现第二个也缺)。"""
    monkeypatch.setenv(resources.ENV_ROOT, str(tmp_path))
    gaps = dict(resources.missing())
    assert set(gaps) == set(resources.REQUIRED)
    assert all(p.is_absolute() for p in gaps.values())


def test_unknown_layout_key_is_a_loud_error():
    try:
        resources.path("nope")
    except KeyError as exc:
        assert "nope" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("拼错的布局键必须报错")


def test_marker_still_points_at_a_real_file():
    """资源根靠 MARKER 认, 它必须真的存在且住在 LAYOUT 的 configs 下。"""
    assert resources.MARKER == pathlib.Path(resources.LAYOUT["configs"]) / "default.yaml"
    assert (resources.root() / resources.MARKER).is_file()
