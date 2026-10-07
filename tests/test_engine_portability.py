"""引擎"整块搬走"必须是被验证的事实, 不是承诺。

做法: 把 `docanon_contract` + 某个引擎包拷进临时目录, 让子进程在**只有这两样**的环境里
import 这个引擎; 同时在 `PYTHONPATH` 最前面放三个陷阱文件(`docanon_core` 与另外两个引擎),
谁偷偷跨包 import 谁就立刻炸。

三个引擎包各跑一遍: 搬运后能 import、且陷阱本身有效 —— 这样"这个包能独立拿走"是被跑出来的,
而不是写在文档/README 里的。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
PKGS = REPO / "packages"
CONTRACT = "docanon_contract"
ENGINE_PKGS = {
    "docanon-engine-ocr": "docanon_engine_ocr",
    "docanon-engine-ner-onnx": "docanon_engine_ner_onnx",
    "docanon-engine-ner-llm": "docanon_engine_ner_llm",
}
TRAP = 'raise RuntimeError("这个引擎跨包 import 了 {name} —— 它并不独立, 搬不走")\n'


def _lift(tmp_path: pathlib.Path, keep: str) -> pathlib.Path:
    """把契约 + 指定引擎包拷到 tmp; 其余 docanon 包一律换成会抛异常的陷阱。"""
    for dist in (f"docanon-contract", keep):
        shutil.copytree(PKGS / dist / "src" / dist.replace("-", "_"), tmp_path / dist.replace("-", "_"))
    for name in ["docanon_core", *ENGINE_PKGS.values()]:
        if (tmp_path / f"{name}.py").exists() or (tmp_path / name).exists():
            continue
        (tmp_path / f"{name}.py").write_text(TRAP.format(name=name), encoding="utf-8")
    return tmp_path


def _run(tmp_path: pathlib.Path, code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize("dist", sorted(ENGINE_PKGS))
def test_engine_can_be_lifted_out_whole(tmp_path, dist):
    pkg = ENGINE_PKGS[dist]
    _lift(tmp_path, dist)
    proc = _run(tmp_path, f"import {pkg}; print('lifted', {pkg}.__name__)")
    assert proc.returncode == 0, f"{dist} 搬走后 import 失败:\n{proc.stderr}"
    assert f"lifted {pkg}" in proc.stdout


def test_traps_actually_fire(tmp_path):
    """护栏: 陷阱有效 —— 否则上面那三条测试可能只是"碰巧没触发"。"""
    _lift(tmp_path, "docanon-engine-ocr")
    # 契约是**真的**被拷进来了(引擎本来就依赖它), 所以只检查"别的包"被拦住
    for name in ("docanon_core", "docanon_engine_ner_llm", "docanon_engine_ner_onnx"):
        proc = _run(tmp_path, f"import {name}")
        assert proc.returncode != 0, f"陷阱 {name} 没起作用"
        assert "搬不走" in proc.stderr
