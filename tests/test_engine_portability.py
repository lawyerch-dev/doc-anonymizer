"""引擎"整块搬走"必须是被验证的事实, 不是承诺。

做法: 把 `contract.py` + `engines/` 拷进一个临时包(名字叫 `lifted`), 在子进程里逐个 import
每个引擎模块; 同时在 `PYTHONPATH` 最前面放一个**陷阱** `docanon.py` —— 只要哪个引擎偷偷
import 了 app 侧的 `docanon.*`, 子进程立刻炸, 测试就红。

这样"拷 engines/ + contract.py 就能走"这句话是被跑出来的, 而不是写在文档里的。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "docanon"

ENGINE_MODULES = (
    "lifted.engines.ocr",
    "lifted.engines.ocr_image",
    "lifted.engines.onnx_ner",
    "lifted.engines.llm.client",
    "lifted.engines.llm.ner",
)

TRAP = (
    '"""陷阱: 被搬走的引擎不许 import app 侧的 docanon.*。"""\n'
    'raise RuntimeError("引擎 import 了 docanon 包 —— 它并不独立, 搬不走")\n'
)


def _lift(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "docanon.py").write_text(TRAP, encoding="utf-8")  # 影子模块, 排在 site-packages 之前
    pkg = tmp_path / "lifted"
    shutil.copytree(SRC / "engines", pkg / "engines")
    shutil.copy(SRC / "contract.py", pkg / "contract.py")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    return pkg


def test_engines_can_be_lifted_out_whole(tmp_path):
    """拷 contract.py + engines/ 到别处, 不带 docanon 包也能全部 import。"""
    _lift(tmp_path)
    code = "import importlib\n" + "".join(
        f"importlib.import_module({mod!r})\n" for mod in ENGINE_MODULES
    ) + "print('lifted ok')\n"

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"搬走后的引擎 import 失败:\n{proc.stderr}"
    assert "lifted ok" in proc.stdout


def test_the_trap_actually_fires(tmp_path):
    """护栏: 陷阱本身有效 —— 否则上面那条测试可能只是"碰巧没触发"。"""
    _lift(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-c", "import docanon"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "搬不走" in proc.stderr
