"""Web 界面偏好(「选文件夹」收哪些类型这类): 读 / 结构校验 / 原子写。

为什么不放浏览器 localStorage: 打包成 `.app` 后它属于**软件设置**的一部分 —— 换台机器、清 WebView
数据、或以后换 bundle id 都不该丢, 也能跟方案一起备份。落点走布局表的 `settings` 键
(数据根下的 `var/settings.json`), 与模型、用户方案同属"可写状态"(见 `resources.WRITABLE`)。

**默认值不在这里**: 界面默认(收哪几档、要不要遍历子目录)只有一处真相 —— 前端
`apps/web/src/lib/uploadPrefs.ts`。文件不存在就返回 `{}`, 由界面用自己的默认值; 这里只存"用户改过的"。
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import resources


class SettingsError(ValueError):
    """偏好非法(结构不对 / 有不认识的键)。"""


def path() -> Path:
    return resources.path("settings")


def load() -> dict:
    """读偏好。没有文件(从没改过)返回 `{}`; 读坏了报错, 不装作"用户没设过"。"""
    p = path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SettingsError(f"{p} 读取/解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"{p} 顶层不是对象")
    return data


def save(data: dict) -> dict:
    """结构校验 + 原子写(与 `profiles.save_profile` 同一套做法: 不留半个文件)。"""
    clean = validate(data)
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return clean


def validate(data: dict) -> dict:
    """只认认识的键与形状。

    不认识的键直接报错而不是丢掉: 静默丢掉会让人以为"设了、生效了"(加一项偏好时这里也跟着改)。
    """
    if not isinstance(data, dict):
        raise SettingsError("设置必须是对象")
    unknown = sorted(set(data) - {"upload"})
    if unknown:
        raise SettingsError(f"不认识的设置项: {', '.join(unknown)}（已认识: upload）")
    out: dict = {}
    upload = data.get("upload")
    if upload is None:
        return out
    if not isinstance(upload, dict):
        raise SettingsError("upload 必须是对象")
    exts = upload.get("extensions")
    if not isinstance(exts, list) or not all(isinstance(e, str) and e.startswith(".") for e in exts):
        raise SettingsError("upload.extensions 必须是「.」开头的字符串列表")
    recursive = upload.get("recursive")
    if not isinstance(recursive, bool):
        raise SettingsError("upload.recursive 必须是布尔")
    out["upload"] = {"extensions": exts, "recursive": recursive}
    return out
