#!/usr/bin/env bash
# 首次准备(幂等): 建 venv → 装五个包 → 把字节码缓存重定向到 var/pycache
#
# 为什么要有第 3 步: 默认每个包/测试目录都会长出一个 __pycache__, 满树都是。
# 实测"完全不写字节码"每次要重编译所有导入(整套测试 5.12s → 6.24s), 而"重定向"既保留
# 字节码带来的启动速度, 又只有一处可清理的缓存(var/ 已在 .gitignore 里, 一条规则覆盖)。
#
# 用法: ./scripts/setup_dev.sh                  (已有 .venv 时只补装缺失的部分)
# 可覆盖: PYTHON=python3.12 VENV_DIR=/别处/.venv ./scripts/setup_dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3.12}"
VENV="${VENV_DIR:-.venv}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[1/3] 建虚拟环境: $VENV ($($PY -V 2>/dev/null || echo "$PY"))"
  "$PY" -m venv "$VENV"
else
  echo "[1/3] 已有 $VENV, 跳过创建"
fi

echo "[2/3] 安装五个包与测试依赖(editable)"
"$VENV/bin/pip" install -q -r requirements-dev.txt

echo "[3/3] 把字节码缓存重定向到 var/pycache"
SITE="$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
mkdir -p var/pycache
# 把仓库根直接写进钩子(venv 在仓库外时, "向上找标记"找不到); 仓库搬走后靠向上找兜底
cat > "$SITE/sitecustomize.py" <<PYEOF
"""由 doc-anonymizer 的 scripts/setup_dev.sh 装进 venv: 字节码缓存统一落到 var/pycache。

默认每个包/测试目录都会长出一个 __pycache__; 重定向后源码树保持干净, 又保留字节码的启动速度。
显式设了 PYTHONPYCACHEPREFIX 的环境照旧优先(Python 启动时已填好 sys.pycache_prefix, 这里不覆盖)。
仓库搬走/venv 不属于本仓库时, 什么都不做(那就退回默认行为)。
"""
import os
import sys
from pathlib import Path

_BAKED_REPO = r"$ROOT"


def _repo_root():
    baked = Path(_BAKED_REPO)
    if (baked / "configs" / "default.yaml").is_file():
        return baked
    for parent in Path(__file__).resolve().parents:  # 仓库搬走后: 向上找标记
        if (parent / "configs" / "default.yaml").is_file():
            return parent
    return None


if sys.pycache_prefix is None and not os.environ.get("PYTHONPYCACHEPREFIX"):
    _root = _repo_root()
    if _root is not None:
        sys.pycache_prefix = str(_root / "var" / "pycache")
PYEOF

echo
echo "就绪。缓存会落在 var/pycache(不是源码树)。"
echo "  全量测试: $VENV/bin/python -m pytest -q"
echo "  CLI/Web:  $VENV/bin/docanon run ./samples -o var/out -c configs/onnx.yaml"
