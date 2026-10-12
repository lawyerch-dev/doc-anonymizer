"""界面偏好(`var/settings.json`): 读写 / 结构校验。

为什么要单独落盘: 它是"这台机器上怎么用"的设置(收件规则), 打包成 .app 后换机器/清 WebView 数据
都不该丢 —— 所以走数据根下的文件, 而不是浏览器 localStorage。默认值仍在前端(这里只存用户改过的)。
"""
from __future__ import annotations

import json

import pytest

from docanon_core.server import settings


@pytest.fixture
def store(tmp_path, monkeypatch):
    """落到 tmp_path, 免得动仓库里的 var/settings.json。"""
    target = tmp_path / "var" / "settings.json"
    monkeypatch.setattr(settings, "path", lambda: target)
    return target


def test_missing_file_means_no_preference_yet(store):
    """从没改过 → 空对象(界面用自己的默认值), 不是"报错"也不是"给一份默认值"。"""
    assert settings.load() == {}
    assert not store.exists()


def test_roundtrip_writes_under_the_data_root(store):
    saved = settings.save({"upload": {"extensions": [".pdf", ".png"], "recursive": True}})

    assert saved["upload"]["extensions"] == [".pdf", ".png"]
    assert store.is_file()
    assert json.loads(store.read_text(encoding="utf-8")) == saved
    assert settings.load() == saved


def test_write_is_atomic(store):
    """不留半个文件: 临时的 .tmp 用完就该没了。"""
    settings.save({"upload": {"extensions": [], "recursive": False}})
    assert list(store.parent.glob("*.tmp")) == []


@pytest.mark.parametrize("bad", [
    {"upload": {"extensions": ["pdf"], "recursive": False}},   # 忘了点
    {"upload": {"extensions": [".pdf"], "recursive": "yes"}},   # recursive 不是布尔
    {"upload": {"extensions": ".pdf", "recursive": False}},     # extensions 不是列表
    {"upload": []},                                            # upload 不是对象
    {"upload": {"extensions": [], "recursive": False}, "nope": 1},  # 不认识的键: 报错而不是丢掉
    [],
])
def test_validate_rejects_bad_shapes(store, bad):
    with pytest.raises(settings.SettingsError):
        settings.save(bad)
    assert not store.exists(), "校验没过就不该落盘"


def test_corrupt_file_is_reported_not_swallowed(store):
    store.parent.mkdir(parents=True)
    store.write_text("{ not json", encoding="utf-8")
    with pytest.raises(settings.SettingsError):
        settings.load()
