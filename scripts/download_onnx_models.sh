#!/usr/bin/env bash
# 取两个 ONNX NER 模型到 var/models/onnx/ (gyr66 通用中文 NER + pii-engineer 中文 PII, 约 830MB)
#
# 为什么要镜像: configs/onnx.yaml(日常推荐路线)要这两个模型, 而官方 huggingface.co 在部分网络下
# 不可达(本机实测 20s 超时); hf-mirror.com 可达且实测 6.3MB/s。用 HF_ENDPOINT 可换任意兼容端点。
#
# 用法: ./scripts/download_onnx_models.sh [--check] [--only gyr66|pii-engineer] [--dest 目录]
#   --check   只探测每个文件是否存在(不下载), 用来判断当前端点通不通
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
DEST="$ROOT/var/models/onnx"
CHECK=0
ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1 ;;
    --only) ONLY="${2:?--only 需要模型名}"; shift ;;
    --dest) DEST="${2:?--dest 需要目录}"; shift ;;
    *) echo "未知参数: $1（用 --check / --only / --dest）" >&2; exit 2 ;;
  esac
  shift
done

# 仓库|本地目录名|必需文件（与 configs/onnx.yaml 引用的目录一致）
CATALOG="
protectai/gyr66-bert-base-chinese-finetuned-ner-onnx|gyr66|config.json model.onnx special_tokens_map.json tokenizer.json tokenizer_config.json vocab.txt
pii-engineer/PII-Engineer-Chinese-NER-v1.0|pii-engineer|config.json model.onnx model.onnx.data tokenizer.json tokenizer_config.json
"

# 单文件下载: 先写 .part 再改名 —— 半截文件绝不能被当成"已下好"
fetch() {
  local url="$1" dest="$2"
  if [ -s "$dest" ]; then
    printf '  跳过(已有)  %s\n' "$(basename "$dest")"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  if ! curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 -o "$dest.part" "$url"; then
    rm -f "$dest.part"
    printf '  下载失败  %s\n' "$url" >&2
    return 1
  fi
  mv "$dest.part" "$dest"
  printf '  ✓ %-24s %s\n' "$(basename "$dest")" "$(du -h "$dest" | cut -f1)"
}

probe() {
  local url="$1" code
  code="$(curl -sIL -o /dev/null -w '%{http_code}' --max-time 25 "$url" 2>/dev/null || echo 000)"
  if [ "$code" = "200" ]; then
    printf '  200  %s\n' "$url"
  else
    printf '  %s  %s\n' "$code" "$url" >&2
    return 1
  fi
}

fail=0
while IFS='|' read -r repo name files; do
  [ -n "$repo" ] || continue
  [ -z "$ONLY" ] || [ "$ONLY" = "$name" ] || continue

  echo "== $name  ($repo)"
  for f in $files; do
    url="$ENDPOINT/$repo/resolve/main/$f"
    if [ "$CHECK" = "1" ]; then probe "$url" || fail=1; else fetch "$url" "$DEST/$name/$f" || fail=1; fi
  done

  if [ "$CHECK" = "0" ] && [ -d "$DEST/$name" ]; then
    for f in $files; do
      if [ ! -s "$DEST/$name/$f" ]; then
        echo "  缺文件: $DEST/$name/$f" >&2
        fail=1
      fi
    done
    echo "  合计 $(du -sh "$DEST/$name" | cut -f1)"
  fi
done <<< "$CATALOG"

if [ "$fail" != "0" ]; then
  echo >&2
  echo "有文件没拿到。换个端点再试, 例如:" >&2
  echo "  HF_ENDPOINT=https://huggingface.co $0" >&2
  exit 1
fi

echo
if [ "$CHECK" = "1" ]; then
  echo "端点可用: ${ENDPOINT}（文件都在; 去掉 --check 即开始下载）"
else
  echo "模型就位: ${DEST}"
  echo "  确认: .venv/bin/docanon engines -c configs/onnx.yaml"
fi
