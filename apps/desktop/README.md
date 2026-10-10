# apps/desktop — 桌面壳 (Tauri v2)

把本地 Python 服务 + Web UI 装进一个原生窗口。**开发与测试都不需要它**：
`.venv/bin/python -m pytest`、`.venv/bin/docanon run`、`.venv/bin/docanon web` 三条命令就够，
壳只是同一套 UI 的窗口包装。壳里那套渲染由 `tests/e2e/webkit/`（Playwright 的 WebKit 内核）覆盖。

**要发给别人的东西只有它**（`npm run dist:desktop`，见下）—— 其余入口都是给改代码的人用的。

用**系统 WebView**（macOS = WKWebView）而不是内置 Chromium：打包体积小一个数量级，
而且与浏览器端看到的是同一个内核，不用维护两套渲染。

壳本身是 Rust（`src-tauri/src/`），只做四件事：找资源根 → 起 Python 侧车 → 等 `/health` → 把窗口切过去。
界面、引擎、产物一律归 Python 侧，壳不参与业务。

## 运行（需 Rust 工具链）

```bash
rustup --version          # 没有就装: https://rustup.rs
cd apps/desktop
npm install               # @tauri-apps/cli（壳的构建器，由 npm 提供，不用 cargo install）
npm run dev               # = tauri dev；等价于仓库根的 npm run dev:desktop
```

主进程 `src-tauri/src/backend.rs` 会：用 `.venv` 的 Python 跑 `docanon_core.cli web`（默认端口 **8770**、
`configs/onnx.yaml`；五个包已 editable 装进 `.venv`，所以不需要再拼 `PYTHONPATH`），
等 `/health` 就绪后把窗口切到 `http://127.0.0.1:8770`。

壳的编译输出全在 `src-tauri/target/`（与仓库根的 `build/` 无关，已 gitignore）。

## 后端的出生与死亡（三条实测出来的约束）

1. **项目根是找出来的，不是数 `..` 出来的**。dev 产物在 `src-tauri/target/<profile>/` 里，层数随 profile 变，
   固定层数会指进 `target/` 内部 —— 那样会拿系统 `python3` 去起后端，报一堆 `ModuleNotFoundError`。
   现在和 Python 侧一样，从可执行文件逐级向上找带 `configs/default.yaml` 的目录；找不到直接报错。
2. **壳被强杀时后端必须自己了断**。窗口关 / 进程退出只能覆盖"正常退出"这条路，强杀时这里根本不会执行。
   spawn 时带上 `DOCANON_EXIT_WITH_PARENT=1`，由
   `packages/docanon-core/src/docanon_core/server/lifecycle.py` 的父进程监视盯住：macOS 靠 `getppid()`
   变号（父死被 reparent），Windows 没有 reparent，那边用 `OpenProcess` 探活
   （`packages/docanon-core/tests/test_server.py` 锁这条，两条路各一条测试）。
3. **只认自己拉起的那个后端**。端口上要是蹲着别人的 docanon（旧孤儿），`/health` 会回它自己的 pid，
   壳发现对不上就直接报错，不会用别人的服务开出一个假窗口（关窗时也就不会杀错进程）。

## 启动页（Tauri 版新增的一条）

窗口**先开出来**、加载本地 `web/index.html`，等 `/health` 就绪后再 `navigate` 到真实界面；
起不来则由 Rust 调页面的 `window.__docanonFail(...)` 把原因显示在窗口里。

为什么反过来做：等就绪才开窗，首次使用（要先加载本地引擎）就是**双击后黑屏等着**，
看起来完全像坏了 —— 而从不看终端的人根本看不到 stderr 里那句报错。

## 可覆盖的环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DOCANON_ROOT` | 源码树向上查找 / 包内 `docanon/` | 资源根（只读：configs、web、samples、vendor） |
| `DOCANON_DATA` | 源码态不设；打包态见下 | 可写状态根（下载的模型、用户自建方案） |
| `DOCANON_PYTHON` | 包内 sidecar → `<root>/.venv` 的 python → `python3` | 后端解释器（覆盖它就等于强制走源码态） |
| `DOCANON_CONFIG` | `configs/onnx.yaml` | 配置文件（相对资源根） |
| `DOCANON_PORT` | `8770` | 服务端口 |

`DOCANON_DATA` 在各平台按系统习惯落：macOS `~/Library/Application Support/docanon`、
Windows `%LOCALAPPDATA%\docanon`、Linux `$XDG_DATA_HOME/docanon`。

**为什么资源与可写状态要分家**：打包后资源根在安装目录内部，首次运行还可能被 macOS 的
App Translocation 挂到只读随机路径 —— 模型写到那儿不是失败就是被清掉。分家由
`resources.WRITABLE` 定义（`models` / `user_configs`），壳只负责把 `DOCANON_DATA` 指对地方。

## 图标

`icon.svg`（源，手改）→ `scripts/make_app_icon.sh` → `icon.iconset/`（1024 源）→
`tauri icon` → `src-tauri/icons/`（`.icns`/`.ico`/各尺寸 PNG）。
**两份产物都要提交**：它们是打包输入，而 `rsvg-convert` 只在装了 librsvg 的机器上才有。
`make_app_icon.sh --check` 会核对尺寸与 icns/ico 是否都在。

几何按 macOS 图标网格（1024 画布、圆角方块占 824 居中、圆角 185），配色取自
`packages/ui/src/theme.css` 的 brand 三档 —— 与界面里的内联 Logo 同源，别单独调色。

## 打包

```bash
npm run dist:desktop      # = ./scripts/dev.sh dist, 几分钟(两个平台都是这一条)
```

**必须在本平台上打**：PyInstaller 不做交叉编译，Tauri 也只出宿主平台的原生包 —— 所以 Mac 上只能出
macOS 包、Windows 上只能出 Windows 包。官方包由
[`.github/workflows/build-desktop.yml`](../../.github/workflows/build-desktop.yml)
在 `macos-15` 与 `windows-latest` 两个 runner 上并行打出，传到 GitHub Release。

| 平台 | 产物 | 用户拿到后 |
|---|---|---|
| macOS（**仅 Apple Silicon**） | `doc-anonymizer_<版本>_aarch64.dmg` | 拖进「应用程序」→ 首次**右键 →「打开」** |
| Windows（x64） | `doc-anonymizer_<版本>_x64-setup.exe` | 双击安装 → SmartScreen 点**「更多信息」→「仍要运行」** |

**只发 Apple Silicon**：Intel Mac 不在支持范围内（没有任何 x64 产物）。
**不签名不公证**（两个平台首次打开都要手工放行一次）；Hutch 时代就是这样，换 Tauri 没改变这一点 ——
要改得买 Apple 开发者账号（$99/年）。

体积账：安装包与解包后都远小于 Electrobun 版 —— 不再有"首次启动往
`~/Library/Application Support/dev.docanon.app/` 解出约 700MB"这一步（Tauri 是原生二进制，不自解包）。
模型另算（5.9G，首次使用按方案下载，不进包）。

实测出来的约束：

1. **资源根必须经 `bundle.resources` 收进包**。Tauri 只认**本项目**（`apps/desktop`）内的路径，
   所以 `dev.sh dist` 先把资源摆到 `stage/docanon`（镜像仓库布局，已被 .gitignore），由
   `src-tauri/tauri.dist.conf.json` 整体收成包内的 `docanon/`（macOS 落在 `Contents/Resources/`，
   Windows 与可执行文件同级）。壳用 `paths.rs` 的 `PACKAGED_MARKER` 认它，找不到就报错退出。
   **dist 配置单独一个文件**（`tauri.dist.conf.json`）而不是塞进主配置：`stage/` 只在打包时存在，
   放进主配置会让日常 `tauri dev` 直接因为"资源路径不存在"起不来。
2. **侧车用 onedir 不用 onefile**。onefile 的引导器会 fork 出真正的进程，`child.pid` 与 `/health`
   报的 pid 对不上，壳会判成"端口被别的实例占了"直接退出（`sidecar/docanon-server.spec` 里有说明）。
   Tauri 复制资源时会保留可执行位（实测 `755` 进包还是 `755`），否则会出现"装上了但后端起不来"。
3. **模型不进包**（5.9G）：首次使用由界面上的「初始化」按方案下载到 `DOCANON_DATA`。
4. **OCR 权重必须在打包前下好**。它是 rapidocr "第一次用的时候"下到 `site-packages` 的；CI 是干净
   环境，不显式下就会打出一个没有权重的空壳，而运行时会试图往只读的安装目录里写。`dev.sh dist` 里有这一步。
5. **`DOCANON_EXIT_WITH_PARENT` 在 Windows 上得换机制**（见上：reparent vs `OpenProcess`）。
6. **打包目标要按平台显式给**（`--bundles app,dmg` / `--bundles nsis`）。Tauri 默认打"该平台支持的全部"，
   Windows 上那会连 MSI 一起打（要临时下 WiX，慢且易抖）；而我们把未验证的目标明确停手，
   不装作支持。

还有两条是**踩过才知道**的基础设施脾气：

- **`hdiutil` 在 CI 上偶发 `create failed - Resource busy`**（造 dmg 的最后一步）。同一份代码连跑两次，
  一次成功一次就栽在这，跟代码无关。`dev.sh dist` 因此给这一步留了最多 3 次重试。
- **Release 的资产筛选要兜住"一个都没匹配到"**。产物名现在是 `*.dmg` 与 `*-setup.exe`（真·安装器，
  不再是"zip 里装个 exe"），但筛选漏空在网页上完全看不出来 —— 所以匹配不到就 exit 1。

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

**结果（Safari/26.6, AppleWebKit 605.1.15）**：file-viewer 预览渲染正常、脱敏前后对比正常、浅色、**零控制台错误**；
抖动基线（8 秒内）`dimsUnique:["466x559"]`、`scrollUnique:[28]`、`resizes8s:1` —— 稳定，没有可见跳动。

> 历史：换过四轮壳。`Electron`（内置 Chromium，与开发浏览器同内核）→ `Tauri`（曾因 WKWebView 下
> PDF 抖动被弃，commit `67330ba`）→ `Electrobun`（系统 WebView + 自解包，对 Windows 的分发体验差：
> 产物是"zip 里装个 `Setup.exe`"，且每个用户首次启动要往用户目录解出约 700MB）→ `Tauri v2`（现在）。
> 当初那个 PDF 抖动没有在 Electrobun 上复现，也没有在现在的 `jitter-check.mjs` 基线里复现 ——
> 它不是这个内核的必然结果。Electron 壳代码在 `82dc18f` 与删除前的 git 历史里可查。
