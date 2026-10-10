#!/usr/bin/env bash
# 从一份 file-viewer 资源树里删掉"本产品不预览的格式"的资源。
#
# 为什么有它: @file-viewer/web-full 是"全格式"包(约 232MB), 而本产品只处理
# doc/docx/xls/xlsx/ppt/pdf 与 txt/csv/md/图片 —— drawio / CAD / Typst / Adobe 设计件 /
# STEP-IGES 这些资源运行时**永远不会被请求**(格式路由见 apps/web/src/lib/viewer.ts),
# 却会让每个安装包白胖 169MB。
#
# 用法: ./scripts/prune_file_viewer.sh <file-viewer 目录>
#
# 只对**进包的副本**调用(见 scripts/dev.sh 的 dist): 本地 `var/vendor/file-viewer` 保持全量 ——
# 开发时预览什么都看得到, 只有收进安装包的那份瘦身。幂等: 删过的目录不在就跳过。
# 只删不改: 不动 manifest、不动 web-full 的 iife 与 renderers(那些是格式路由的分发器)。
set -euo pipefail

target="${1:?用法: $0 <file-viewer 目录>}"
[ -d "$target" ] || { printf '目录不存在: %s\n' "$target" >&2; exit 1; }

# 产品不预览的格式 -> 这些格式专属的资源(目录相对 file-viewer 根)
PRUNED=(
  "vendor/drawio"   # diagrams.net: .drawio/.xml 图表
  "vendor/design"   # Adobe: .ai/.psd/.indd/.xd/.eps
  "wasm/cad"        # .dwg/.dxf/.dwf
  "wasm/typst"      # .typ
  "wasm/model"      # .step/.iges/.brep 三维模型
)

before="$(du -sk "$target" | cut -f1)"
freed=0
for rel in "${PRUNED[@]}"; do
  if [ -d "$target/$rel" ]; then
    size="$(du -sk "$target/$rel" | cut -f1)"
    rm -rf "${target:?}/$rel"
    freed=$((freed + size))
    printf '  裁掉 %-16s %sMB\n' "$rel" "$((size / 1024))"
  fi
done

after="$(du -sk "$target" | cut -f1)"
if [ "$freed" = "0" ]; then
  printf 'file-viewer 已是裁剪后的形态: %s (无需处理)\n' "$target"
else
  printf 'file-viewer 裁剪完成: %s → %s (省 %sMB)\n' \
    "$((before / 1024))MB" "$((after / 1024))MB" "$((freed / 1024))"
fi
