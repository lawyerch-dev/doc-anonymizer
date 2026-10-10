# apps/desktop — 桌面壳 (Electrobun)

把本地 Python 服务 + Web UI 装进一个原生窗口。**开发与测试都不需要它**：
`.venv/bin/python -m pytest`、`.venv/bin/docanon run`、`.venv/bin/docanon web` 三条命令就够，
壳只是同一套 UI 的窗口包装。壳里那套渲染由 `tests/e2e/webkit/`（Playwright 的 WebKit 内核）覆盖。

**要发给别人的东西只有它**（`npm run dist:desktop`，见下）—— 其余入口都是给改代码的人用的。

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
   `docanon_core/server/lifecycle.py` 的 `_watch_parent` 盯住 `getppid()`（父进程一死就被 reparent），
   SIGKILL 壳也照样回收（`packages/docanon-core/tests/test_server.py` 锁这条）。
3. **只认自己拉起的那个后端**。端口上要是蹲着别人的 docanon（旧孤儿），`/health` 会回它自己的 pid，
   壳发现对不上就直接报错退出，不会用别人的服务开出一个假窗口。

## 可覆盖的环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DOCANON_ROOT` | 源码树向上查找 / 包内 `docanon/` | 资源根（只读：configs、web、samples、vendor） |
| `DOCANON_DATA` | = 资源根；打包态 = `~/Library/Application Support/docanon` | 可写状态根（下载的模型、用户自建方案） |
| `DOCANON_PYTHON` | 包内 sidecar → `<root>/.venv/bin/python` → `python3` | 后端解释器（覆盖它就等于强制走源码态） |
| `DOCANON_CONFIG` | `configs/onnx.yaml` | 配置文件（相对资源根） |
| `DOCANON_PORT` | `8770` | 服务端口 |

**为什么资源与可写状态要分家**：打包后资源根在 `.app` 里面，首次运行还可能被 macOS 的
App Translocation 挂到只读随机路径 —— 模型写到那儿不是失败就是被清掉。分家由
`resources.WRITABLE` 定义（`models` / `user_configs`），壳只负责把 `DOCANON_DATA` 指对地方。

## 图标

`icon.svg`（源，手改）→ `scripts/make_app_icon.sh` → `icon.iconset/`。
Hutch 的 `mac.icons` 默认就吃 `icon.iconset`（它自己用 `iconutil` 转 `.icns`），**iconset 要提交**：
它是打包输入，而 `rsvg-convert` 只在装了 librsvg 的机器上才有。

几何按 macOS 图标网格（1024 画布、圆角方块占 824 居中、圆角 185），配色取自
`packages/ui/src/theme.css` 的 brand 三档 —— 与界面里的内联 Logo 同源，别单独调色。

## 打可分发版

```bash
npm run dist:desktop      # = ./scripts/dev.sh dist, 几分钟
```

产物：`build/stable-macos-arm64/doc-anonymizer.app` 与 `build/artifacts/*.dmg`（实测各约 211MB / 214MB）。
它现在是**自包含**的：`.app` 里带 PyInstaller 打出的 Python 侧车与资源根（configs / web / samples /
vendor 232MB），换台没装 Python 的机器、放到 `/tmp` 或「应用程序」里都能跑。

体积账要分清：**下载 211MB，但首次启动会在 `~/Library/Application Support/dev.docanon.app/` 解出
约 700MB**（Electrobun 的自解包要留一份未压缩的 tar，那是它更新/卸载机制的底座）。模型另算，见下。

三条实测出来的约束：

1. **资源根必须走 Hutch 的 `copy` 进包**。Hutch 的 `copy` 只认本项目（`apps/desktop`）内的路径，
   所以 `dev.sh dist` 先把资源摆到 `stage/docanon`（镜像仓库布局，已被 .gitignore），由
   `electrobun.config.ts` 整体收成包内的 `Contents/Resources/app/docanon`。
2. **侧车用 onedir 不用 onefile**。onefile 的引导器会 fork 出真正的进程，`child.pid` 与 `/health`
   报的 pid 对不上，壳会判成"端口被别的实例占了"直接退出（`docanon-server.spec` 里有说明）。
3. **模型不进包**（5.9G）：首次使用由界面上的「初始化」按方案下载到 `DOCANON_DATA`。

还没做、也知道的缺口：**没签名没公证**（发给别人首次打开要被 Gatekeeper 拦一次，右键 →「打开」）；
**「最准」那一档要大模型**，得用户自己下 GGUF，且必须本机装了 `llama.cpp`（侧车的 PATH 里补了
`/opt/homebrew/bin`，双击启动也能找到 brew 装的 `llama-server`）。

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
