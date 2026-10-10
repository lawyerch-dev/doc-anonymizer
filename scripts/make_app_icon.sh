#!/usr/bin/env bash
# 由 apps/desktop/icon.svg 生成 apps/desktop/icon.iconset/ —— Electrobun 的 `mac.icon`
# 默认就吃这个目录(它自己会用 iconutil 转成 .icns), 所以这里只出 PNG, 不自己打 .icns。
#
# 为什么把 iconset 也提交进仓库: 它是**打包输入**而不是运行期可再生资产(不进 var/),
# 而且 rsvg-convert 只在装了 librsvg 的机器上有 —— 不提交的话, 换台机器就打不出图标了。
#
# 用法: scripts/make_app_icon.sh [--check]   # --check 只校验 iconset 与 svg 是否同步(给守卫用)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SVG="$ROOT/apps/desktop/icon.svg"
OUT="$ROOT/apps/desktop/icon.iconset"

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
  echo "app 图标: iconset 齐(${#SIZES[@]} 组倍率)"
  exit 0
fi

command -v rsvg-convert >/dev/null || { echo "缺 rsvg-convert: brew install librsvg"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
for s in "${SIZES[@]}"; do
  rsvg-convert -w "$s" -h "$s" -o "$OUT/icon_${s}x${s}.png" "$SVG"
  rsvg-convert -w "$((s * 2))" -h "$((s * 2))" -o "$OUT/icon_${s}x${s}@2x.png" "$SVG"
done

echo "已生成 $OUT:"
ls -1 "$OUT"
