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
  desktop              起桌面壳(Electrobun, 系统 WebView; 首次自动 hutch install)
  test [pytest 参数]   跑测试(默认 -q)
  cli  <docanon 参数>  直接调 docanon, 例: ./scripts/dev.sh cli run ./samples -o var/out
  engines [配置文件]   看这份配置实际加载了哪些引擎(默认 configs/onnx.yaml)
  models [额外参数]    取 ONNX NER 模型到 var/models/onnx(约 830MB; 默认走 hf-mirror 镜像)
  docs                 起文档站(apps/docs: Next.js + velora 组件, 首次自动 npm install)
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

cmd_docs() {
  has npm || die "文档站要 node/npm: 装 node 后重试(或只用 .venv/bin/docanon web 那个产品界面)"
  cd apps/docs
  [ -d node_modules ] || { say "首次: npm install(约 1 分钟)…"; npm install --no-audit --no-fund; }
  say "→ http://127.0.0.1:3000    (Ctrl+C 停止; 构建静态站: npm run build → apps/docs/out)"
  exec npm run dev
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
  desktop) cmd_desktop ;;
  test) cmd_test "$@" ;;
  cli) cmd_cli "$@" ;;
  engines) cmd_engines "$@" ;;
  models) cmd_models "$@" ;;
  docs) cmd_docs ;;
  doctor) cmd_doctor ;;
  help | -h | --help) usage ;;
  *) usage; exit 1 ;;
esac
