#!/usr/bin/env bash
# 启动本地大模型 (llama.cpp 的 llama-server, OpenAI 兼容)
# 用法: ./scripts/serve_llm.sh [端口] [模型路径]
set -euo pipefail

PORT="${1:-8080}"
MODEL="${2:-models/Qwen3.8-4B-Q4_K_M.gguf}"
CTX="${CTX:-8192}"

if [ ! -f "$MODEL" ]; then
  echo "找不到模型文件: $MODEL"
  echo "请先下载: ./scripts/download_model.sh"
  exit 1
fi

echo "启动 llama-server"
echo "  模型: $MODEL"
echo "  端口: $PORT   上下文: $CTX"
echo "  接口: http://127.0.0.1:$PORT/v1"

exec llama-server \
  -m "$MODEL" \
  --alias qwen3.8-4b \
  -c "$CTX" \
  -ngl 99 \
  --host 127.0.0.1 \
  --port "$PORT"
