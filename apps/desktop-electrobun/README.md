# apps/desktop-electrobun — Electrobun 原型壳

Electron 的**轻量替代**：用**系统 WebView**（macOS = WKWebView/WKWebKit），打包体积小。
本原型目的：验证「file-viewer + Web UI」在系统 WebView 下能否正常工作。

## 兼容性验证（已做）

用 Playwright 的 **WebKit 引擎**（与 WKWebView 同内核）跑了一遍完整流程：

```bash
# 先起本地服务
docanon web -p 8803 -c configs/onnx.yaml
# 再跑检测
cd apps/desktop-electrobun/compat && npm install && npx playwright install webkit
DOCANON_URL=http://127.0.0.1:8803 node webkit-check.mjs
```

**结果（Safari/26.6, AppleWebKit 605.1.15）**：file-viewer 预览渲染正常、脱敏前后对比正常、浅色、**零控制台错误** → 系统 WebView 可行。

## 运行壳（需 Hutch 工具链）

Electrobun 用自有 CLI **Hutch**（Bun 生态）：

```bash
curl -fsSL https://hutch.blackboard.sh/hutch/install.sh | sh
cd apps/desktop-electrobun
hutch install
hutch electrobun dev        # 或 npm start
```

主进程 `src/bun/index.ts` 会：拉起 `.venv` 的 Python 跑 `docanon web`（端口 8771、`configs/onnx.yaml`），
等 `/health` 就绪后开窗加载 `http://127.0.0.1:8771`。

## 与 Electron 壳对比

| | Electron (`apps/desktop`) | Electrobun (本目录) |
|---|---|---|
| 体积 | 大（内置 Chromium） | 小（系统 WebView + zstd） |
| 内核 | Chromium（与开发环境一致） | WKWebView（Safari 引擎） |
| 工具链 | Node/npm（成熟） | Hutch + Bun（较新） |

`DOCANON_PYTHON / DOCANON_CONFIG / DOCANON_PORT` 与 Electron 壳一致。
