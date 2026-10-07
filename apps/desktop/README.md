# apps/desktop — 桌面壳 (Electrobun)

把本地 Python 服务 + Web UI 装进一个原生窗口。**开发与测试都不需要它**：
`.venv/bin/python -m pytest`、`.venv/bin/docanon run`、`.venv/bin/docanon web` 三条命令就够，
壳只是同一套 UI 的窗口包装。壳里那套渲染由 `tests/e2e/webkit/`（Playwright 的 WebKit 内核）覆盖。

用**系统 WebView**（macOS = WKWebView）而不是内置 Chromium：打包体积小一个数量级。

## 运行（需 Hutch 工具链）

Hutch 是 Electrobun 自带的 CLI（Bun 生态）：

```bash
curl -fsSL https://hutch.blackboard.sh/hutch/install.sh | sh
cd apps/desktop
hutch install
hutch electrobun dev        # 或 npm start / npm run build
```

主进程 `src/bun/index.ts` 会：用 `.venv` 的 Python 跑 `docanon_core.cli web`（默认端口 **8770**、
`configs/onnx.yaml`；五个包已 editable 装进 `.venv`，所以不需要再拼 `PYTHONPATH`），
等 `/health` 就绪后开窗加载 `http://127.0.0.1:8770`。

`hutch.lock` 要提交（钉住 `@types/bun`）；`.hutch/`、`build/`、`node_modules/` 都在 .gitignore 里。

## 后端的出生与死亡（三条实测出来的约束）

1. **项目根是找出来的，不是数 `..` 出来的**。dev 构建产物在 `<root>/apps/desktop/build/**.app` 里面，
   固定层数会指进 `.app` 包内部 —— 那样会拿系统 `python3` 去起后端，报一堆 `ModuleNotFoundError`。
   现在和 Python 侧一样，从本文件逐级向上找带 `configs/default.yaml` 的目录；找不到直接报错退出。
2. **壳被强杀时后端必须自己了断**。Electrobun 的 SIGTERM quit 序列不触发窗口 close / `process.exit`，
   实测会留下孤儿后端占住 8770。spawn 时带上 `DOCANON_EXIT_WITH_PARENT=1`，由
   `docanon/server.py` 的 `_watch_parent` 盯住 `getppid()`（父进程一死就被 reparent），
   SIGKILL 壳也照样回收（`tests/test_server.py` 锁这条）。
3. **只认自己拉起的那个后端**。端口上要是蹲着别人的 docanon（旧孤儿），`/health` 会回它自己的 pid，
   壳发现对不上就直接报错退出，不会用别人的服务开出一个假窗口。

## 可覆盖的环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DOCANON_ROOT` | 源码树向上查找 | 项目根（也是 Python 侧的资源根） |
| `DOCANON_PYTHON` | `<root>/.venv/bin/python`（退回 `python3`） | Python 解释器 |
| `DOCANON_CONFIG` | `configs/onnx.yaml` | 配置文件（相对资源根） |
| `DOCANON_PORT` | `8770` | 服务端口 |

## 系统 WebView 兼容性验证（已做）

用 Playwright 的 **WebKit 引擎**（与 WKWebView 同内核）跑完整流程：

```bash
# 先起本地服务
docanon web -p 8803 -c configs/onnx.yaml
# 再跑检测
cd tests/e2e/webkit && npm install && npx playwright install webkit
DOCANON_URL=http://127.0.0.1:8803 node webkit-check.mjs                      # 功能(默认走 sample.docx)
DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node webkit-check.mjs # 换格式(如 PDF)
DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node jitter-check.mjs # 抖动
```

**结果（Safari/26.6, AppleWebKit 605.1.15）**：file-viewer 预览渲染正常、脱敏前后对比正常、浅色、**零控制台错误**。

> 历史：曾有一个 Electron 壳（内置 Chromium，与开发浏览器同内核）和一个 Tauri 壳。
> Tauri 因 WKWebView 下 PDF 抖动被弃（commit `67330ba`），Electron 因体积与"每个平台两套内核"
> 被 Electrobun 取代（Electron 壳代码在 `82dc18f`/删除前的 git 历史里可查）。

## 打包(后续)

`hutch electrobun build`；Python 后端仍需打成 sidecar（PyInstaller 单文件）一起分发。
