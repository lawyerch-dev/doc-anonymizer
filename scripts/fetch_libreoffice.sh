#!/usr/bin/env bash
# 取 LibreOffice 到 var/libreoffice/(不进包; 与 file-viewer/模型同模式)。
# 默认走国内镜像(腾讯云); 换镜像: DOCANON_LIBREOFFICE_MIRROR=... ./scripts/fetch_libreoffice.sh
# 用法: ./scripts/fetch_libreoffice.sh [版本]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-25.8.7}"
MIRROR="${DOCANON_LIBREOFFICE_MIRROR:-https://mirrors.cloud.tencent.com/libreoffice/libreoffice}"
DEST="$ROOT/var/libreoffice"
mkdir -p "$DEST"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
base="$MIRROR/stable/${VER}"
os="$(uname -s)"
arch="$(uname -m)"
case "$os" in
  Darwin)
    if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
      url="$base/mac/aarch64/LibreOffice_${VER}_MacOS_aarch64.dmg"
    else
      url="$base/mac/x86_64/LibreOffice_${VER}_MacOS_x86-64.dmg"
    fi
    echo "下载 $url"
    curl -fL "$url" -o "$tmp/lo.dmg"
    mkdir -p "$tmp/mnt"
    hdiutil attach "$tmp/lo.dmg" -mountpoint "$tmp/mnt" -nobrowse
    rm -rf "$DEST/LibreOffice.app"
    cp -R "$tmp/mnt/LibreOffice.app" "$DEST/"
    hdiutil detach "$tmp/mnt"
    xattr -dr com.apple.quarantine "$DEST/LibreOffice.app" || true
    ;;
  Linux)
    command -v dpkg-deb >/dev/null 2>&1 || {
      echo "需要 dpkg-deb 解包官方 deb(apt 系自带; 没有就手动装 LibreOffice 并设 DOCANON_SOFFICE)" >&2
      exit 1
    }
    url="$base/deb/x86_64/LibreOffice_${VER}_Linux_x86-64_deb.tar.gz"
    echo "下载 $url"
    curl -fL "$url" -o "$tmp/lo.tar.gz"
    tar -xzf "$tmp/lo.tar.gz" -C "$tmp"
    # 官方 deb 包里只有 DEBS/*.deb, 没有现成的 program/soffice, 得逐个解出来
    for deb in "$tmp"/LibreOffice_*/DEBS/*.deb; do
      dpkg-deb -x "$deb" "$tmp/unpack"
    done
    # 解出的 trees 形如 opt/libreoffice*/program/soffice; 拷进 DEST 保留结构
    cp -R "$tmp/unpack/opt/." "$DEST/"
    ;;
  *)
    echo "不支持的平台: $os —— 手动装 LibreOffice 并设 DOCANON_SOFFICE" >&2
    exit 1
    ;;
esac
echo "完成: $DEST"
echo "自检: ./scripts/dev.sh doctor"
