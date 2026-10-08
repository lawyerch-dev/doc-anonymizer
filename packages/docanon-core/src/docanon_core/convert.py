"""旧版二进制 Office(.doc/.xls/.wps) -> 现代格式(.docx/.xlsx), 借 LibreOffice headless。

这不是"引擎": 它不产出 Block, 只把文件换个格式; 抽取由被委托的抽取器完成。
soffice 走"系统优先 -> var/libreoffice(下载)"，不进包。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import resources

# 源后缀 -> (soffice --convert-to 目标格式, 产物后缀)
TARGETS: dict[str, tuple[str, str]] = {
    ".doc": ("docx", ".docx"),
    ".wps": ("docx", ".docx"),
    ".xls": ("xlsx", ".xlsx"),
}
LEGACY_EXTENSIONS: tuple[str, ...] = tuple(TARGETS)

_CONVERT_TIMEOUT = 120
_MAC_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")


def _usable(p: Path) -> bool:
    """存在且可执行才算数 —— 只 is_file() 会把一个不可执行的文件当成可用。"""
    return p.is_file() and os.access(p, os.X_OK)


def find_soffice() -> Path | None:
    """按 环境变量 > 系统安装 > var/libreoffice(下载) 的顺序找 soffice。

    显式设了 `DOCANON_SOFFICE` 就以它为准: 是坏路径也**不**回退系统安装 ——
    悄悄换一个二进制比直接报错更难排查。
    """
    override = os.environ.get("DOCANON_SOFFICE")
    if override:
        p = Path(override).expanduser()
        return p if _usable(p) else None
    found = shutil.which("soffice")
    if found:
        return Path(found)
    if _usable(_MAC_SOFFICE):
        return _MAC_SOFFICE
    bundled = resources.path("libreoffice")
    if bundled.is_dir():
        hits = [p for p in sorted(bundled.rglob("soffice")) if _usable(p)]
        if hits:
            return hits[0]
    return None


def unavailable_reason() -> str | None:
    """可用返回 None; 否则给可操作的缺失原因(坏掉的显式覆盖要点名)。"""
    if find_soffice() is not None:
        return None
    override = os.environ.get("DOCANON_SOFFICE")
    if override:
        return f"缺 LibreOffice: DOCANON_SOFFICE 指向的 soffice 不存在({override})"
    return (
        "缺 LibreOffice(soffice): 装一个, 或运行 ./scripts/fetch_libreoffice.sh, "
        "或设 DOCANON_SOFFICE 指向它"
    )


def to_modern(src: Path, workdir: Path) -> tuple[Path, str]:
    """把 src 转成现代格式, 返回 (产物路径, 产物后缀)。失败抛 RuntimeError。"""
    suffix = src.suffix.lower()
    try:
        target, out_ext = TARGETS[suffix]
    except KeyError:
        raise RuntimeError(f"不是可转换的旧格式: {src.suffix or '无扩展名'}") from None
    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(unavailable_reason())
    before = {p.name for p in workdir.glob("*")}
    profile = (workdir / "lo-profile").as_posix()
    try:
        proc = subprocess.run(
            [str(soffice), "--headless", "--norestore",
             f"-env:UserInstallation=file://{profile}",
             "--convert-to", target, "--outdir", str(workdir), str(src)],
            capture_output=True, text=True, timeout=_CONVERT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"LibreOffice 转换超时(>{_CONVERT_TIMEOUT}s): {suffix} -> {target}"
        ) from exc
    produced = [
        p for p in workdir.glob("*")
        if p.name not in before and p.suffix.lower() == out_ext
    ]
    if proc.returncode != 0 or not produced:
        detail = (proc.stderr or proc.stdout or "无输出").strip()
        raise RuntimeError(f"LibreOffice 转换失败({suffix} -> {target}): {detail[:200]}")
    return produced[0], out_ext
