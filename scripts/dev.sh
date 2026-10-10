#!/usr/bin/env bash
# 开发一键入口 —— ./scripts/dev.sh <命令>
#
# 为什么有它: 开发时"装依赖 / 起 Web / 起桌面壳 / 跑测试"都该是一条命令, 而且失败时直接告诉你缺什么。
# 它不引入任何新工具, 只是把已有命令包了一层(底层还是 setup_dev.sh / docanon / hutch / pytest),
# 所以文档里写 dev.sh 与写底层命令都成立 —— 底层命令出问题时可以直接用它们排查。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEFAULT_PORT=8000
DEFAULT_CONFIG="configs/onnx.yaml"

say() { printf '%s\n' "$*"; }
die() { printf '错误: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
用法: ./scripts/dev.sh <命令> [参数...]

  setup                一条命令装好环境(幂等): venv + 五个包 + 预览资源 + 缓存重定向
  web  [docanon 参数]  起 Web 界面(默认 -p 8000 -c configs/onnx.yaml)
  webui                产品界面开发态(后端 + Vite dev server + 代理; 生产形态用 web)
  desktop              起桌面壳(Electrobun, 系统 WebView; 首次自动 hutch install)
  test [pytest 参数]   跑测试(默认 -q)
  cli  <docanon 参数>  直接调 docanon, 例: ./scripts/dev.sh cli run ./samples -o var/out
  engines [配置文件]   看这份配置实际加载了哪些引擎(默认 configs/onnx.yaml)
  models [额外参数]    取 ONNX NER 模型到 var/models/onnx(约 830MB; 默认走 hf-mirror 镜像)
  website              起官网+文档站(website/: Astro + Starlight + @doc-anonymizer/ui, 首次自动 npm install)
  dist                 打可分发版(macOS: .app/.dmg; Windows: -Setup.exe; 自带 Python 侧车与资源; 慢, 几分钟)
  doctor               环境自检: 缺什么、为什么起不来

例:
  ./scripts/dev.sh setup            # 第一次
  ./scripts/dev.sh web              # 起界面 → http://127.0.0.1:8000
  ./scripts/dev.sh desktop          # 起桌面壳
  ./scripts/dev.sh test packages/docanon-core/tests/test_job.py
EOF
}

# ---- 公共检查 ----

need_venv() {
  if [ ! -x .venv/bin/python ]; then
    say "没有 .venv —— 先跑一次 setup(装五个包, 约 20 秒)…"
    ./scripts/setup_dev.sh
  fi
}

has() { command -v "$1" >/dev/null 2>&1; }

# 仓库的 python: DOCANON_PYTHON 优先(CI 用它指向 runner 自己的 python, 省掉建 venv 这一步),
# 否则用 venv —— Windows 的 venv 把可执行文件放在 Scripts/ 下, 名字也不同。
# 打可分发版要用它: 五个包得装在同一个解释器里, 用错一个就会在 PyInstaller 那步报缺模块。
py_cmd() {
  if [ -n "${DOCANON_PYTHON:-}" ]; then
    printf '%s' "$DOCANON_PYTHON"
  elif [ -x .venv/bin/python ]; then
    printf '%s' .venv/bin/python
  elif [ -x .venv/Scripts/python.exe ]; then
    printf '%s' .venv/Scripts/python.exe
  elif has python3; then
    printf '%s' python3
  elif has python; then
    printf '%s' python
  else
    return 1
  fi
}

# 拷贝目录树。macOS 的 `cp -c`(APFS 写时复制)是秒级 —— 500MB 的资源摆一次不拖慢每次构建;
# git-bash 的 GNU cp 没有 -c, 会立刻报错, 于是退回真拷(多花十几秒)。
copy_tree() {
  cp -Rc "$1" "$2" 2>/dev/null || cp -R "$1" "$2"
}

warn_if_no_onnx_models() {
  if [ -z "$(ls -A var/models/onnx 2>/dev/null || true)" ]; then
    say "提示: var/models/onnx 是空的 —— configs/onnx.yaml 的 onnx_ner 会起不来。"
    say "      取模型(约 830MB, 走 hf-mirror 镜像): ./scripts/dev.sh models"
    say "      只用规则+词典也行: ./scripts/dev.sh web -c configs/default.yaml"
  fi
}

# ---- 子命令 ----

cmd_setup() {
  ./scripts/setup_dev.sh

  if [ -d var/vendor/file-viewer ]; then
    say "预览资源已就位: var/vendor/file-viewer"
  elif has npm; then
    say ""
    say "预览资源缺失: var/vendor/file-viewer(约 232MB, 只影响 Web 的预览区; 不想现在下就 Ctrl+C)"
    ./scripts/fetch_file_viewer.sh
  else
    say "预览资源缺失且没装 npm —— 跳过。装上 npm 后跑: ./scripts/fetch_file_viewer.sh"
  fi

  if [ -z "$(ls -A var/models/onnx 2>/dev/null || true)" ]; then
    say ""
    say "还没有 ONNX 模型(约 830MB)。要中文人名/机构识别就跑一次: ./scripts/dev.sh models"
  fi

  say ""
  cmd_doctor
}

cmd_web() {
  need_venv
  local args=("$@")
  if [ ${#args[@]} -eq 0 ]; then
    warn_if_no_onnx_models
    args=(-p "$DEFAULT_PORT" -c "$DEFAULT_CONFIG")
  fi

  local port="$DEFAULT_PORT"
  local i
  for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[$i]}" in
      -p | --port) port="${args[$((i + 1))]:-$port}" ;;
    esac
  done

  say "→ http://127.0.0.1:$port    (Ctrl+C 停止)"
  exec .venv/bin/docanon web "${args[@]}"
}

# 产品界面的开发态: 后端(docanon web) + Vite dev server 并发跑, Vite 把 /api /samples /uploads /outputs /file-viewer /health 六条前缀代理给后端。
# 生产形态不这样跑 —— 那是 `npm run build:web && ./scripts/dev.sh web`。
cmd_webui() {
  need_venv
  has npm || die "产品界面的开发态要 node/npm: 装 node 后重试(或只起后端: ./scripts/dev.sh web)"
  [ -d node_modules ] || { say "首次: 根目录 npm install(npm workspaces: ui + website + apps/web)…"; npm install --no-audit --no-fund; }

  local port="$DEFAULT_PORT"
  # 后端 docanon web 只发 apps/web/dist; 缺它后端会 SystemExit(1), Vite 代理随之静默 404 ——
  # 这是"少一层必须报错, 不许静默"那条硬边界, 所以在起后端之前先拦下来。
  [ -f apps/web/dist/index.html ] || die "缺 apps/web/dist/index.html —— 后端 docanon web 会因此起不来, Vite 代理会静默 404。先构建: npm run build:web（或 npm run setup）"
  warn_if_no_onnx_models
  say "→ 开发请开 http://127.0.0.1:5173 (Vite 热更, 别开 :$port —— 那是后端, 且是旧构建产物)   (Ctrl+C 停止)"
  say "  (后端 :$port 是 Vite 的代理目标, 不弹浏览器 —— 由 Vite 转发 /api 等)"

  # --no-browser: 别自动弹标签页; 开发看的是 :5173 的 Vite 实时页, 弹 :$port 的旧构建只会误导
  .venv/bin/docanon web -p "$port" -c "$DEFAULT_CONFIG" --no-browser &
  # 故意不是 local: EXIT trap 在函数返回之后才跑, 那时局部变量已出栈 —— set -u 下会报
  # "未绑定的变量"并跳过 kill, 后端就孤儿化占住 8000。做成全局变量才能在任何退出路径收走它。
  backend_pid=$!
  # 任何退出路径都要收走后端, 否则它孤儿化占住 8000(下次开就报端口被占)
  trap 'kill "$backend_pid" 2>/dev/null || true' EXIT INT TERM
  DOCANON_BACKEND="http://127.0.0.1:$port" npm run dev -w @doc-anonymizer/web
}

cmd_desktop() {
  need_venv
  if ! has hutch; then
    die "没装 Hutch(Electrobun 的 CLI)。装:
  curl -fsSL https://hutch.blackboard.sh/hutch/install.sh | sh
只用浏览器的话不需要壳: ./scripts/dev.sh web"
  fi

  cd apps/desktop
  if [ ! -d node_modules ]; then
    say "首次: hutch install(装壳的 JS 依赖)…"
    hutch install
  fi
  say "→ 桌面壳启动中(系统 WebView; 后端 http://127.0.0.1:8770)…"
  exec npm start
}

cmd_test() {
  need_venv
  if [ $# -eq 0 ]; then
    set -- -q
  fi
  exec .venv/bin/python -m pytest "$@"
}

cmd_cli() {
  need_venv
  [ $# -gt 0 ] || die "给个 docanon 子命令, 例: ./scripts/dev.sh cli run ./samples -o var/out -c configs/onnx.yaml"
  exec .venv/bin/docanon "$@"
}

cmd_models() {
  exec ./scripts/download_onnx_models.sh "$@"
}

# 可分发版: 把 Python 后端(PyInstaller 侧车)与资源根一起塞进安装包, 让产物脱离仓库也能跑。
#
# macOS 与 Windows **都走这里**(CI 也是), 所以这个函数里不许出现平台专属命令:
# 解释器走 `py_cmd`、拷贝走 `copy_tree`、产物报告只 glob 不写死名字。
# 顺序不能换: 侧车与资源都先摆到 apps/desktop/stage/docanon(Hutch 的 `copy` 只认本项目内的路径),
# 由 apps/desktop/electrobun.config.ts 整体收进包里的 `docanon/`(macOS 在 Contents/Resources/app 下)。
# 模型**不进包**(5.9G): 首次使用由界面上的"初始化"按方案下载到用户数据目录(见壳里的 DOCANON_DATA)。
cmd_dist() {
  has npm || die "打可分发版要 node/npm: 装 node 后重试"
  has hutch || die "打可分发版要 Hutch(Electrobun 的 CLI)。装:
  macOS/Linux: curl -fsSL https://hutch.blackboard.sh/hutch/install.sh | sh
  Windows:     irm https://hutch.blackboard.sh/hutch/install.ps1 | iex"

  local py; py="$(py_cmd)" || die "找不到 python —— 先跑 ./scripts/setup_dev.sh(或设置 DOCANON_PYTHON)"
  "$py" -c "import docanon_core" 2>/dev/null || die "$py 里没有 docanon —— 先跑一次 ./scripts/setup_dev.sh"

  # 少了预览资源, 发出去的包预览区全空白 —— 那是"少一层"。缺了就现在拉(CI 是干净环境, 一定缺),
  # 拉完还没有就停手: 宁可现在不打, 也不发一个预览全空白的包出去。
  if [ ! -d var/vendor/file-viewer ]; then
    say "预览资源缺失(232MB), 先拉一次…"
    ./scripts/fetch_file_viewer.sh
  fi
  [ -d var/vendor/file-viewer ] || die "预览资源还是没到位 —— 发出去的包预览区会全空白, 先跑 ./scripts/fetch_file_viewer.sh"
  # 图标是提交进仓库的打包输入; 缺了就现生成(要 rsvg-convert, 只在装了 librsvg 的机器上有)
  [ -f apps/desktop/icon.png ] || ./scripts/make_app_icon.sh
  # Hutch 要求 win.icon 的 PNG ≤256px(ICO 的上限), 给大了 Windows 构建会直接失败
  # (`invalid Windows PNG icon: PngTooLarge`)。用 python 读 PNG 头校验 —— 跨平台,
  # 而且**两个平台的打包都拦得住**, 不会等到 Windows 那一趟才发现。
  "$py" - <<'PY' || die "apps/desktop/icon.png 必须是 256×256 的 PNG(Windows 图标的硬限制, 见 make_app_icon.sh)"
import pathlib
import struct

raw = pathlib.Path("apps/desktop/icon.png").read_bytes()
assert raw[:8] == b"\x89PNG\r\n\x1a\n", "不是 PNG"
w, h = struct.unpack(">II", raw[16:24])
assert (w, h) == (256, 256), f"现在是 {w}x{h}"
PY

  say "== 1/5 前端产物 =="
  npm run build:web

  say "== 2/5 Python 侧车(PyInstaller; 首次会装它并分析依赖, 约 1 分钟) =="
  "$py" -c "import PyInstaller" 2>/dev/null || "$py" -m pip install -q pyinstaller
  # OCR 权重默认是"第一次用的时候"从网上下到 site-packages 里的。这里必须先下好, 否则打进
  # 侧车的是个**没有权重的空壳**, 而运行时会试图往只读的安装目录里写 —— 那等于 OCR 直接坏。
  "$py" - <<'PY' || die "OCR 权重没下成(要联网) —— 没有它, 打出来的包识别不了图片/扫描件"
import pathlib
import rapidocr
from rapidocr.utils.download_models import download_models

models = pathlib.Path(rapidocr.__file__).parent / "models"
if not any(models.glob("*.onnx")):
    download_models()
PY
  "$py" -m PyInstaller --noconfirm --clean \
    --distpath apps/desktop/build/sidecar --workpath apps/desktop/build/pyi-work \
    apps/desktop/sidecar/docanon-server.spec >/dev/null

  say "== 3/5 摆资源根(镜像仓库布局, 供 resources.LAYOUT 解析) =="
  local stage=apps/desktop/stage/docanon
  rm -rf apps/desktop/stage
  mkdir -p "$stage/configs" "$stage/apps/web" "$stage/var/vendor" "$stage/samples" "$stage/sidecar"
  copy_tree configs/.                        "$stage/configs/"
  copy_tree apps/web/dist                    "$stage/apps/web/dist"
  copy_tree samples/.                        "$stage/samples/"
  copy_tree var/vendor/file-viewer           "$stage/var/vendor/file-viewer"
  copy_tree apps/desktop/build/sidecar/docanon-server/. "$stage/sidecar/"

  say "== 4/5 装壳的 JS 依赖(仅首次) =="
  [ -d apps/desktop/node_modules ] || (cd apps/desktop && hutch install)

  say "== 5/5 打安装包(把上面这棵树压进包里, 慢的就是这一步) =="
  (cd apps/desktop && npm run build)

  say ""
  say "完成, 产物:"
  # 产物名随平台变(.app/.dmg vs -Setup.exe), 只 glob 不写死 —— 写死的名字在另一个平台上会静默不报
  du -sh apps/desktop/build/artifacts/* 2>/dev/null | sed 's/^/  /' || true
  ls -d apps/desktop/build/*/doc-anonymizer.app 2>/dev/null | sed 's/^/  /' || true
  say ""
  say "自测(脱离仓库也能跑): 把产物拷到 /tmp(「下载」)里双击。"
  say "发给别人: 未签名 —— macOS 首次要右键→「打开」, Windows 要「更多信息」→「仍要运行」。"
}

cmd_website() {
  has npm || die "官网/文档站要 node/npm: 装 node 后重试(或只用 .venv/bin/docanon web 那个产品界面)"
  [ -d node_modules ] || { say "首次: 根目录 npm install(npm workspaces: ui + website)…"; npm install --no-audit --no-fund; }
  say "→ http://127.0.0.1:3000    (Ctrl+C 停止; 静态站: npm run build -w @doc-anonymizer/website → apps/website/out)"
  exec npm run dev -w @doc-anonymizer/website
}

cmd_engines() {
  need_venv
  local cfg="${1:-$DEFAULT_CONFIG}"
  exec .venv/bin/docanon engines -c "$cfg"
}

cmd_doctor() {
  local ok="✓" no="✗"

  say "== 环境 =="
  if [ -x .venv/bin/python ]; then
    say "  $ok .venv            $(.venv/bin/python -V 2>&1)  ($ROOT/.venv)"
  else
    say "  $no .venv            缺 —— 跑 ./scripts/setup_dev.sh"
  fi
  if [ -x .venv/bin/python ]; then
    if .venv/bin/python - <<'PY' >/dev/null 2>&1
import importlib.metadata as md
import docanon_contract, docanon_core, docanon_engine_ocr, docanon_engine_ner_onnx, docanon_engine_ner_llm  # noqa: F401
assert all(md.version(d) for d in ("docanon-core", "docanon-contract", "docanon-engine-ocr",
                                   "docanon-engine-ner-onnx", "docanon-engine-ner-llm"))
PY
    then
      say "  $ok 五个包          已装(editable): $(.venv/bin/python -c 'import importlib.metadata as m; print(m.version("docanon-core"))')"
    else
      say "  $no 五个包          导入失败 —— 跑 ./scripts/setup_dev.sh"
    fi
  fi
  for c in python3.12 npm node hutch; do
    if has "$c"; then say "  $ok $c$(printf '%*s' $((16 - ${#c})) '')$(command -v "$c")"; else say "  · $c 缺(可选)"; fi
  done

  say "== 资产 =="
  local d
  if [ -f apps/web/dist/index.html ]; then
    say "  $ok apps/web/dist     产品界面已构建"
  else
    say "  $no apps/web/dist     缺 —— docanon web 起不来; 跑: npm run build:web"
  fi
  for d in var/vendor/file-viewer var/models/onnx/gyr66 var/models/onnx/pii-engineer; do
    if [ -d "$d" ]; then say "  $ok $d"; else say "  $no $d   缺"; fi
  done
  local gguf
  gguf="$(ls var/models/*.gguf 2>/dev/null | wc -l | tr -d ' ')"
  say "  · var/models/*.gguf  $gguf 个(LLM 路线需要; 用 ./scripts/download_model.sh 拉)"

  if [ ! -d var/vendor/file-viewer ]; then
    say "     → 预览区会 404: ./scripts/fetch_file_viewer.sh"
  fi
  if [ -z "$(ls -A var/models/onnx 2>/dev/null || true)" ]; then
    say "     → onnx_ner 起不来, 取模型: ./scripts/dev.sh models"
  fi

  say "== 旧格式转换(LibreOffice) =="
  local soffice_hit=""
  if [ -n "${DOCANON_SOFFICE:-}" ] && [ -x "${DOCANON_SOFFICE}" ]; then
    soffice_hit="DOCANON_SOFFICE=$DOCANON_SOFFICE"
  elif command -v soffice >/dev/null 2>&1; then
    soffice_hit="系统: $(command -v soffice)"
  elif [ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    soffice_hit="/Applications/LibreOffice.app"
  elif [ -n "$(find var/libreoffice -name soffice -type f 2>/dev/null | head -n1)" ]; then
    soffice_hit="var/libreoffice(下载)"
  fi
  if [ -n "$soffice_hit" ]; then
    say "  $ok soffice            $soffice_hit"
  else
    say "  $no soffice            缺 —— .doc/.xls/.wps 将记 unsupported; 取: ./scripts/fetch_libreoffice.sh"
  fi

  say "== 引擎(configs/onnx.yaml 实际加载了什么) =="
  if [ -x .venv/bin/docanon ]; then
    .venv/bin/docanon engines -c "$DEFAULT_CONFIG" || say "  (engines 自检没跑通, 上面就是原因)"
  else
    say "  (还没装 docanon)"
  fi
}

# ---- 分发 ----

cmd="${1:-help}"
shift || true

case "$cmd" in
  setup) cmd_setup ;;
  web) cmd_web "$@" ;;
  webui) cmd_webui ;;
  desktop) cmd_desktop ;;
  test) cmd_test "$@" ;;
  cli) cmd_cli "$@" ;;
  engines) cmd_engines "$@" ;;
  models) cmd_models "$@" ;;
  website) cmd_website ;;
  dist) cmd_dist ;;
  doctor) cmd_doctor ;;
  help | -h | --help) usage ;;
  *) usage; exit 1 ;;
esac
