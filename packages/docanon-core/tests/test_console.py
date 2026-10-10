"""控制台输出的编码边界。

Windows 上 stdio 的默认编码跟着控制台代码页走(cp1252 / GBK), 而 docanon 的输出 —— 进度、
命中统计、清单路径 —— 全是中文。CI 实测: Windows 上 `docanon run samples` 崩在第一句
`print("待处理 11 个文件 ...")`, UnicodeEncodeError 把整个进程带走。

macOS/Linux 默认就是 utf-8, 所以这个坑本地永远看不见 —— 它是被 CI 那步"用包内侧车跑一遍
样例"抓出来的。这条测试把边界锁在**任何平台**都能跑: 造一个 cp1252 的 stdout 就行。
"""
from __future__ import annotations

import io
import sys

from docanon_core import cli


def test_console_output_is_forced_to_utf8(monkeypatch):
    """cp1252 的 stdout 必须被掰成 utf-8, 否则中文一打就崩。"""
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))

    cli._ensure_utf8_output()

    assert sys.stdout.encoding.replace("-", "").lower() == "utf8"
    print("待处理 11 个文件 -> var/out")   # 这一步在修复前就是 UnicodeEncodeError
    sys.stdout.flush()                     # TextIOWrapper 有缓冲, 不刷就看不到字节
    assert "待处理".encode("utf-8") in raw.getvalue(), "中文没有按 utf-8 写出去"


def test_console_encoding_leaves_plain_streams_alone(monkeypatch):
    """stdout 可能是 StringIO 之类(测试、日志重定向): 没得配就安静跳过, 不许因此抛异常。"""
    monkeypatch.setattr(sys, "stdout", io.StringIO())

    cli._ensure_utf8_output()   # 不抛就算过


def test_main_forces_utf8_before_anything_prints(monkeypatch):
    """入口自己要把这件事做掉 —— 不能指望每个调用方记得先配编码。"""
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))

    try:
        cli.main(["--help"])
    except SystemExit:
        pass   # argparse 的 --help 走 SystemExit, 这里只关心编码有没有被配好

    assert sys.stdout.encoding.replace("-", "").lower() == "utf8"
