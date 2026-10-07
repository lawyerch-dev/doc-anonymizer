#!/usr/bin/env bash
# 下载本地大模型 (默认从 ModelScope 国内镜像, 快)
# 用法: ./scripts/download_model.sh [量化]   例如 Q4_K_M / Q5_K_M / Q8_0
set -euo pipefail

QUANT="${1:-Q4_K_M}"
REPO="empero-ai/Qwen3.8-4B-Distill-GGUF"
FILE="Qwen3.8-4B-${QUANT}.gguf"
BASE="https://www.modelscope.cn/models/${REPO}/resolve/master"

mkdir -p var/models
echo "下载 ${FILE} (${BASE}/${FILE})"
curl -L -C - --fail -o "var/models/${FILE}" "${BASE}/${FILE}"
ls -lh "var/models/${FILE}"
