# 产品界面迁移到 Vite + React 设计

> 状态：已批准，待实施
> 日期：2026-10-09
> 现状以 [README](../../README.md)、[AGENTS.md](../../AGENTS.md)、[architecture](../architecture.md) 为准；本文是当时的完整设计。

## 背景与问题

`apps/web/` 现在是**零构建**的手写件：`index.html` + `app.css`（68 行）+ `app.js`（373 行，
`@ts-check` + JSDoc）。功能是齐的（samples 预设、上传、file-viewer 预览、
L1/L2/L3 分层脱敏口径、内联试跑、运行日志、命中统计、原文↔脱敏对照），但**视觉与控件停在裸样式**：
没有设计 token 体系、没有暗色、没有统一状态，控件是原生 `button`/`select`。

与此同时仓库里已经有一套完整的共享组件库 `@doc-anonymizer/ui`（velora 100 组件 + 31 区块 +
shadcn 基础件 + `theme.css` 设计 token，[packages/ui](../../packages/ui/README.md)），
但**只有 `website/` 在用它**。产品界面换 React 栈时正是引同一个包的时机
（[决策笔记](../../.agent/notes/implemented/architecture/2026-10-07-shared-ui-package.md)）。

## 目标与非目标

**目标**

- 把 `apps/web/` 迁到 **Vite 5 + React 19 + TypeScript + Tailwind 4**，复用 `@doc-anonymizer/ui`。
- 视觉与控件达到 ui 包水准；**顺带优化布局**（左栏配置渐进披露、三栏对照、空/加载态、暗色）。

**非目标**

- 不改后端 API 契约与路由语义；不改账本与产物命名。
- **不重做**信息架构与交互流程（不是"重新设计产品"，是"迁移 + 美化 + 布局微调"）。
- 不引入 SSR / 客户端路由框架（单页工具，无需 router）。

**不变量（硬约束）**

1. **运行期零 node、全离线**：`docanon web` 仍只发静态文件，不发 node（[rules/07](../../.agent/rules/07-frontend.md)）。
2. **组件只在 `packages/ui`**：任何 app 里不许出现 velora 组件源码，只许 import
   （[test_docs.py](../../tests/test_docs.py) 守着）。
3. **DOM 契约**：E2E（[webkit-check.mjs](../../tests/e2e/webkit/webkit-check.mjs)、
   [jitter-check.mjs](../../tests/e2e/webkit/jitter-check.mjs)）依赖 `.preset` `#run` `#paneSrc`
   `#paneOut` `#stats`，迁移不得改这些钩子。

## 架构

- **运行期（不变）**：`docanon web` → 静态发 `apps/web/dist`。引擎、账本、离线语义全部不变。
- **构建期（新增）**：`npm run build -w @doc-anonymizer/web`（Vite）产出 `apps/web/dist`。
  React 19 与 ui 包的 peer 对齐，Tailwind 4 走 `@tailwindcss/vite`。
- 根 `package.json` 的 `workspaces` 增加 `apps/web`，与 `packages/ui`、`website` 并列。

## 目录与构建

```
apps/web/
├── index.html              # Vite 入口模板（源）
├── src/
│   ├── main.tsx            # React 挂载
│   ├── App.tsx             # 布局骨架
│   ├── components/         # PresetList / ConfigPanel / PreviewPane / LogModal / StatsCard
│   ├── lib/
│   │   ├── api.ts          # 现有 fetch 调用封成 typed client
│   │   ├── formats.ts      # TEXT_EXT / ENTITY_TYPES / STRATEGIES / EFFECT / locText
│   │   └── viewer.ts       # file-viewer 全局脚本的命令式封装
│   └── styles.css          # @import theme.css + @source 到 packages/ui/src
├── vite.config.ts
├── tsconfig.json
├── package.json            # @doc-anonymizer/web
└── dist/                   # 构建产物（gitignore，不进仓库）
```

- **产物落 `apps/web/dist`**：`resources.LAYOUT["web"]` 从 `apps/web` 改为 `apps/web/dist`
  （[resources.py](../../packages/docanon-core/src/docanon_core/resources.py) 一处改）。
  `REQUIRED` 仍含 `web`，「少一层就报错」的语义不变：dist 缺失时资源根校验直接失败。
- 产物**不进 git**，与 `website/dist` 一致；由 `npm run setup` 构建、`doctor` 检查存在性。
- `emptyOutDir` 用 Vite 默认（安全清空 `dist`），不与源码同层，杜绝"构建覆盖源码"。

## 服务端改动

[routes.py](../../packages/docanon-core/src/docanon_core/server/routes.py)：

- 删掉写死的 `_WEB_ASSETS = {"/app.css": …, "/app.js": …}`。
- 新增静态映射：`/` 与 `/index.html` → `dist/index.html`；`/assets/*` → `dist/assets/*`。
  `_CTYPES` 已覆盖 `.js` `.css` `.woff2` `.svg`，无需扩展。
- `/samples` `/uploads` `/outputs` `/file-viewer` `/api/*` 全部原样保留。
- 不做 history fallback（工具是单入口，无客户端路由）。

## 组件与视觉

- 只 import：`@doc-anonymizer/ui/primitives/*`（button/input/label/…）、
  `@doc-anonymizer/ui/<name>`、需要时 `@doc-anonymizer/ui/blocks/*`。
- `styles.css` 必须 `@import "@doc-anonymizer/ui/theme.css";` 且 `@source` 扫到
  `packages/ui/src`，否则类名被 Tailwind 静默摇掉
  （[复盘 0001](../../.agent/postmortem/0001-tailwind-source-dropped-classes.md)）。
- **布局优化**：左栏（选文档 + 口径 L1/L2/L3，用 accordion 收拢）→ 中（原文）→ 右（脱敏后）；
  窄屏左栏转抽屉。L1/L2/L3 用统一 accordion 承载，替代裸 `<details>`。
- **暗色**：引入 `theme.css` 的 `.dark` token，提供主题切换；跟随系统偏好。
- **DOM 契约保留**：`.preset` `#run` `#paneSrc` `#paneOut` `#stats` 语义与位置不变。
- file-viewer 仍是全局 `window.FlyfishFileViewerWebFull`：用 `useEffect` + ref 封装挂载/清理；
  文本类扩展（`TEXT_EXT`）沿用 `<pre>` 分支。

## 数据流与状态

- 现有 `state`（preset/token/filename/url/trace/configRef/configData/configDirty/modelDirs）
  转 React state（顶层 `App` 持有，子组件按需传入）。
- 所有 fetch 收进 `lib/api.ts`：`presets / configs / configData / models / upload / anonymize /
  save / import / export / delete`，统一抛 `Error`，UI 层统一展示。
- 保留 `localStorage['docanon.config']` 记忆当前口径。

## 兼容性契约

- 后端 API 请求/响应字段**一字不改**：`{preset|token, config}` 入参、`counts`、`trace`
  （`source/extractor/converted_from/config/detectors/timing/detections`）出参。
- `/health`、上传 50MB 上限、中文文件名 `unquote`、旧格式转换的 400+原因语义全部沿用。

## 开发与分发

- `npm run dev`（产品界面）→ **Vite dev server + proxy**：`/api` `/samples` `/uploads`
  `/outputs` `/file-viewer` 代理到后端 `docanon web`（默认 :8000），后端由 `dev.sh` 并发拉起。
- 生产路径：`npm run build -w @doc-anonymizer/web` → `docanon web` 直发 dist。
- `npm run setup` 增加构建 dist；`doctor` 增加"dist 是否存在"检查并给可操作提示。
- `npm run test:web` 增加 `apps/web` 的 `tsc --noEmit` + `vite build`。
- PyInstaller 打包根：打包前必须先构建 dist（否则打包根缺 `web` 资源）。

## 错误处理

保留"不许静默少一层"：引擎预检失败 → 400 + 原因、界面显式报错；列表接口不预检；
上传/脱敏的 loading / disabled 态保留。前端所有 API 错误走统一错误条。

## 测试与守卫

| 项 | 动作 |
|---|---|
| [test_layout.py](../../packages/docanon-core/tests/test_layout.py) | LAYOUT 改后 `web_index()` 断言仍成立（`dist/index.html`） |
| [test_docs.py](../../tests/test_docs.py) | 新 npm scripts 必须写进 README；本设计文档登记进 `RECORDS` |
| 新增守卫 | `apps/web/dist` 存在性（未构建时给出可操作提示，而非运行时才炸） |
| `npm run test:web` | 增加 `apps/web` 的 `tsc --noEmit` + `vite build` |
| E2E webkit | 选择器契约保留 → 不破坏；建议纳入 `before-you-push` |
| 现状文档同步 | README(.en) / CONTRIBUTING(.en) / docs/architecture(.en) / AGENTS.md / rules 03·07 / ui README / website README 的"零构建·三个静态件"表述 |

**构建与测试的先后**（关键，避免自相矛盾）：`test_layout.py` 断言 `resources.missing() == []`
且 `web_index().is_file()`，dist 一旦没构建，Python 全量测试会红。因此：

- `npm run setup` 必须先构建 dist，`npm run test:py` 前置依赖"dist 已构建"；
- 未构建时 `doctor` 与守卫给出的必须是**可操作提示**（"跑 `npm run build -w @doc-anonymizer/web`"），
  而不是等到资源根校验才炸；
- 这正是"少一层就报错"的体现：不静默给空界面。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| dist 缺失导致 `docanon web` 起不来 | `doctor` + 新增存在性守卫明示"跑构建" |
| Tailwind `@source` 漂移、类名静默丢失 | `@source` 指向 `packages/ui/src` + `apps/web/src`，加守卫 |
| E2E DOM 选择器被改坏 | 契约写进 rules，E2E 纳入提交前检查 |
| 新 spec 未登记 `RECORDS` 触发 docs 守卫误伤 | 本文件写入时同步登记 |
| 附带的旧 dist 累积分发 | dist 不进 git；构建前 `emptyOutDir` 清空 |

## 实施步骤概览（交 writing-plans 细化）

1. 脚手架 `apps/web`（Vite + React + TS + Tailwind 4），接入 `theme.css` 与 `@source`。
2. 迁移逻辑：`lib/api.ts` / `lib/viewer.ts` / `lib/formats.ts`，state 转 React。
3. 重建界面：布局优化 + ui 组件 + 暗色 + 空/加载态。
4. 服务端：`resources.LAYOUT["web"]` → `dist`；`routes.py` 静态映射改造。
5. 工程：workspaces、`dev.sh`（dev 并发 + proxy）、`doctor`、`setup`。
6. 守卫与文档：测试更新 + 现状文档同步 + 决策笔记。
