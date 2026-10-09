# Agent Note: 产品前端从零构建迁到 Vite + React

Status: implemented
Date: 2026-10-09

## 问题

`apps/web/` 是零构建的手写件（`index.html` + `app.css` 68 行 + `app.js` 373 行），功能齐但视觉是裸样式；
而仓库里 `@doc-anonymizer/ui`（velora 100 组件 + shadcn 基础件 + 设计 token）只有 `website/` 在用。
"组件抽成共享包"当初的理由就是"产品前端换栈时引同一个包，外观不会分叉" —— 那个换栈时机就是现在。

## 决策

产品界面迁到 **Vite 5 + React 19 + TS + Tailwind 4**，`import` 同一个 `@doc-anonymizer/ui`。
产物落 `apps/web/dist`（gitignore），`resources.LAYOUT["web"]` 改指 `dist`；服务端只改静态映射，API 一字不改。

## 代价与取舍

- **多一条构建链**：`npm run setup` 要先构建；`test:py` 前置 `build:web`（`test_layout.py` 要求
  `dist/index.html` 存在）。换来的是真类型检查、打包压缩与组件复用。
- **运行期仍然零 node**：`docanon web` 还是只发静态文件，离线语义没变。
- **选了 `dist/` 而不是"构建到 apps/web/ 根"**：Vite 的入口模板与产物同名 `index.html`，
  输出到项目根会自我覆盖、`emptyOutDir` 还有清空源码的风险。
- **保留 DOM 契约**（`.preset` `#run` `#paneSrc` `#paneOut` `#stats`）：E2E 按这些选择器跑，
  换框架不能顺手改名。

## 证据

- 设计：`docs/specs/2026-10-09-web-ui-vite-migration-design.md`
- 守卫：`packages/docanon-core/tests/test_{layout,resources,server}.py`、`tests/test_check_scope.py`
- 契约：`tests/e2e/webkit/{webkit-check,jitter-check}.mjs`
