#!/usr/bin/env bash
# 由 apps/desktop/icon.svg 生成图标, 两步:
#   icon.iconset/       —— macOS 那套倍率图(提交进仓库, 也是下一步的输入源)
#   src-tauri/icons/    —— Tauri 各平台的档(.icns/.ico/各尺寸 PNG), 由 tauri icon 从 1024 源切出来
#
# 为什么把产物也提交进仓库: 它们是**打包输入**而不是运行期可再生资产(不进 var/),
# 而且 rsvg-convert 只在装了 librsvg 的机器上才有 —— 不提交的话, 换台机器就打不出图标了。
#
# 与上一版(Electrobun/Hutch)的区别: 不再需要那份 256px 的 icon.png ——
# 那个上限是 Hutch 的 ICO 限制(PngTooLarge), Tauri 自己从 1024 源切 .ico。
#
# 用法: scripts/make_app_icon.sh [--check]   # --check 只校验产物与 svg 是否同步(给守卫用)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SVG="$ROOT/apps/desktop/icon.svg"
OUT="$ROOT/apps/desktop/icon.iconset"
TAURI_ICONS="$ROOT/apps/desktop/src-tauri/icons"

# iconutil 认的就是这套名字(逻辑尺寸 @ 倍率), 名字写错会直接报 "unexpected file"
SIZES=(16 32 128 256 512)

if [[ "${1:-}" == "--check" ]]; then
  [[ -f "$SVG" ]] || { echo "缺 $SVG"; exit 1; }
  for s in "${SIZES[@]}"; do
    for f in "icon_${s}x${s}.png:${s}" "icon_${s}x${s}@2x.png:$((s * 2))"; do
      name="${f%%:*}"; px="${f##*:}"
      [[ -f "$OUT/$name" ]] || { echo "iconset 缺 $name (应为 ${px}px)"; exit 1; }
      got="$(sips -g pixelWidth "$OUT/$name" 2>/dev/null | awk '/pixelWidth/{print $2}')"
      [[ "$got" == "$px" ]] || { echo "$name 尺寸是 ${got}px, 应为 ${px}px"; exit 1; }
    done
  done
  # 打包真正吃的是这两份: macOS 认 .icns, Windows 认 .ico
  for f in icon.icns icon.ico; do
    [[ -f "$TAURI_ICONS/$f" ]] || { echo "缺 src-tauri/icons/$f —— 跑 scripts/make_app_icon.sh 生成"; exit 1; }
  done
  echo "app 图标: iconset 齐(${#SIZES[@]} 组倍率) + src-tauri/icons 的 icns/ico"
  exit 0
fi

command -v rsvg-convert >/dev/null || { echo "缺 rsvg-convert: brew install librsvg"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
for s in "${SIZES[@]}"; do
  rsvg-convert -w "$s" -h "$s" -o "$OUT/icon_${s}x${s}.png" "$SVG"
  rsvg-convert -w "$((s * 2))" -h "$((s * 2))" -o "$OUT/icon_${s}x${s}@2x.png" "$SVG"
done

echo "已生成:"
ls -1 "$OUT"

# 第二步要 Tauri CLI(工作区依赖)。没装就明说, 别留一份过期的 src-tauri/icons 让人以为已经更新了。
if [ -x "$ROOT/node_modules/.bin/tauri" ]; then
  (cd "$ROOT" && npm run icon -w docanon-desktop >/dev/null)
  echo "  src-tauri/icons/ (icns/ico/各尺寸 PNG; 已剔掉用不上的 android/ios)"
  rm -rf "$TAURI_ICONS/android" "$TAURI_ICONS/ios"
else
  echo "注意: 没装工作区依赖, src-tauri/icons 没有重新生成 —— 先跑 npm install 再执行本脚本"
  exit 1
fi
