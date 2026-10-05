# desktop-tauri

Tauri 壳：`std::process::Command` 拉起 `docanon web`（Python sidecar）→ 裸 HTTP 探活 `/health` → 用系统 WKWebView 打开页面；关窗即退出并回收子进程。与 `apps/desktop/main.js`（Electron, Chromium）行为对齐，用于横向比较三种壳。

## 运行

```bash
cd apps/desktop-tauri/src-tauri
cargo tauri dev        # 或 cargo run
```

默认端口 8772（Electron 8770 / Electrobun 8771，互不冲突）。环境变量覆盖：

| 变量 | 默认 |
|---|---|
| `DOCANON_PYTHON` | `<root>/.venv/bin/python`，缺失则 `python3` |
| `DOCANON_ROOT` | 按 `CARGO_MANIFEST_DIR` 推断（打包后需显式给出） |
| `DOCANON_CONFIG` | `configs/onnx.yaml` |
| `DOCANON_PORT` | `8772` |

## 与 Electron 壳的差异

- **外链不走系统浏览器**：Electron 用 `setWindowOpenHandler` 拦 `window.open`；Tauri 里要做同样的事得引入 `tauri-plugin-shell` + 前端配合，原型阶段没加。
- **关窗即退出**（含 macOS）。这是刻意的：常驻的 Python 服务带着 `/health` 和 mapping 接口，无窗口空转等于多一个本地监听面。
- 引擎是 WKWebView 而非 Chromium，`apps/desktop-electrobun/compat/webkit-check.mjs` 就是用来验这一点的。

## 打包

`tauri.conf.json` 里 `bundle.active` 暂为 `false`：产出 `.app` 需要图标（`cargo tauri icon <png>`）和签名/公证配置，且真正的体积大头是 Python venv + onnxruntime + 232MB file-viewer 资源，跟壳选型无关。需要先验打包再补这两项。
