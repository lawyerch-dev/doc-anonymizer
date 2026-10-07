#!/usr/bin/env bash
# 获取 file-viewer 预构建资源(零构建 Web 预览用)
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$DIR/var/vendor/file-viewer"
TMP="$(mktemp -d)"
cd "$TMP"
echo "下载 @file-viewer/web-full ..."
npm pack @file-viewer/web-full >/dev/null 2>&1
tar xzf ./*.tgz
rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
cp -R package/dist "$DEST"
rm -rf "$TMP"
echo "file-viewer 已就位: $DEST"
