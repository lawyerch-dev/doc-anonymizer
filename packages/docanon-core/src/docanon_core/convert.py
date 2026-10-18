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
_IS_WINDOWS = os.name == "nt"
# Windows 上二进制**带扩展名**, 而且 headless 要用控制台版本: 官方启动参数文档写明 soffice.exe 是
# 无控制台的,"命令行/headless 场景要用 soffice.com"。用 .exe 会丢 stdout/stderr、甚至提前返回 ——
# 而 to_modern 靠 returncode 与输出判失败、靠产物判成功, 拿 .exe 会把失败误判成成功。
# 一个元组按优先级排下来即可跨平台通用: 前两个在 mac/Linux 上匹配不到, 无扩展名那个在 Windows 上匹配不到。
_SOFFICE_NAMES = ("soffice.com", "soffice.exe", "soffice")
# Windows 的安装位置(官方文档给的示例是 C:\Program Files\LibreOffice): 安装器**不把 soffice 加进
# PATH**, 所以 which() 命不中, 必须补上固定位置。**这两条路径待真机确认**(见设计 2026-10-18 §5)。
_WIN_PROGRAM_DIRS = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program",
)


def _usable(p: Path) -> bool:
    """存在且可执行才算数 —— 只 is_file() 会把一个不可执行的文件当成可用。

    Windows 没有 Unix 那样的执行位, `os.access(X_OK)` 在那边退化成"文件存在", 所以那边只能退到
    is_file(): 这是**已知的信息损失**, 不是"我们检查过了"。
    """
    if not p.is_file():
        return False
    return True if _IS_WINDOWS else os.access(p, os.X_OK)


def _system_soffice() -> Path | None:
    """系统安装。先问 PATH, 再补各平台的固定位置(两个平台的安装器默认都不改 PATH)。"""
    found = shutil.which("soffice")
    if found:
        p = Path(found)
        # Windows: which() 命中的是 soffice.exe, 同目录必有 soffice.com —— headless 要用那一个
        console = p.with_name(_SOFFICE_NAMES[0])
        if _IS_WINDOWS and _usable(console):
            return console
        return p
    if _IS_WINDOWS:
        for directory in _WIN_PROGRAM_DIRS:
            for name in _SOFFICE_NAMES:
                if _usable(directory / name):
                    return directory / name
        return None
    return _MAC_SOFFICE if _usable(_MAC_SOFFICE) else None


def _bundled_soffice() -> Path | None:
    """`var/libreoffice` 里解出来的那份。按候选名逐个找(Windows 上带扩展名, 直接 rglob("soffice") 一个都找不到)。"""
    base = resources.path("libreoffice")
    if not base.is_dir():
        return None
    for name in _SOFFICE_NAMES:
        for cand in sorted(base.rglob(name)):
            if _usable(cand):
                return cand
    return None


def find_soffice() -> Path | None:
    """按 环境变量 > 系统安装 > var/libreoffice(下载) 的顺序找 soffice。

    显式设了 `DOCANON_SOFFICE` 就以它为准: 是坏路径也**不**回退系统安装 ——
    悄悄换一个二进制比直接报错更难排查。
    """
    override = os.environ.get("DOCANON_SOFFICE")
    if override:
        p = Path(override).expanduser()
        return p if _usable(p) else None
    return _system_soffice() or _bundled_soffice()


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
        # 带上源文件大小: 超时可能是"文件太大"也可能是"卡死", 没有这个数就分不出来
        raise RuntimeError(
            f"LibreOffice 转换超时(>{_CONVERT_TIMEOUT}s): {suffix} -> {target}, "
            f"源文件 {src.stat().st_size / 1_048_576:.1f} MB"
        ) from exc
    candidates = [
        p for p in workdir.glob("*")
        if p.name not in before and p.suffix.lower() == out_ext
    ]
    # 产物挑选必须**确定性**: 撞名时 soffice 会另起一个名字, 而 glob 的顺序随文件系统而异 ——
    # 同一份输入挑到哪个不该靠运气(账本记的路径会跟着漂)。优先源名一致的, 其余按名字排序兜底。
    candidates.sort(key=lambda p: (p.stem != src.stem, p.name))
    if proc.returncode != 0 or not candidates:
        detail = (proc.stderr or proc.stdout or "无输出").strip()
        raise RuntimeError(f"LibreOffice 转换失败({suffix} -> {target}): {detail[:200]}")
    return candidates[0], out_ext
