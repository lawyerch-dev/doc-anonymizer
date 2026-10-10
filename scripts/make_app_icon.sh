#!/usr/bin/env bash
# 由 apps/desktop/icon.svg 生成图标:
#   icon.iconset/  —— macOS 用, Electrobun 的 `mac.icons` 默认就吃它(它自己用 iconutil 转 .icns)
#   icon.png       —— Windows 用(`win.icon` 只吃 .ico 或 .png, 给 PNG 时 Hutch 自己转 ICO)
#
# **icon.png 必须是 256×256**: ICO 的最大边长就是 256, 给大了 Hutch 会直接拒绝并让整个 Windows
# 构建失败(实测 1024 → `invalid Windows PNG icon: PngTooLarge` + exit 1)。--check 会盯住这条。
#
# 为什么把产物也提交进仓库: 它们是**打包输入**而不是运行期可再生资产(不进 var/),
# 而且 rsvg-convert 只在装了 librsvg 的机器上有 —— 不提交的话, 换台机器就打不出图标了。
#
# 用法: scripts/make_app_icon.sh [--check]   # --check 只校验产物与 svg 是否同步(给守卫用)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SVG="$ROOT/apps/desktop/icon.svg"
OUT="$ROOT/apps/desktop/icon.iconset"
PNG="$ROOT/apps/desktop/icon.png"
PNG_PX=256

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
  [[ -f "$PNG" ]] || { echo "缺 $PNG(Windows 图标源)"; exit 1; }
  got="$(sips -g pixelWidth "$PNG" 2>/dev/null | awk '/pixelWidth/{print $2}')"
  [[ "$got" == "$PNG_PX" ]] || { echo "icon.png 是 ${got}px, 必须是 ${PNG_PX}px —— 超过 256 会让 Windows 构建直接失败(PngTooLarge)"; exit 1; }
  echo "app 图标: iconset 齐(${#SIZES[@]} 组倍率) + icon.png ${PNG_PX}px"
  exit 0
fi

command -v rsvg-convert >/dev/null || { echo "缺 rsvg-convert: brew install librsvg"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
for s in "${SIZES[@]}"; do
  rsvg-convert -w "$s" -h "$s" -o "$OUT/icon_${s}x${s}.png" "$SVG"
  rsvg-convert -w "$((s * 2))" -h "$((s * 2))" -o "$OUT/icon_${s}x${s}@2x.png" "$SVG"
done
# ICO 里能放的最大一档就是 256, 所以给 256 —— 给 1024 会被 Hutch 判成 PngTooLarge
rsvg-convert -w "$PNG_PX" -h "$PNG_PX" -o "$PNG" "$SVG"

echo "已生成:"
ls -1 "$OUT"
echo "  $(basename "$PNG") (${PNG_PX}px)"

