# Agent Note: 组件抽成共享包 apps/ui（复用靠包，不靠复制）

Status: implemented

## 问题

第一次集成 velora 时，组件被我**拷进了站点 app**（`apps/docs/src/components/velora/*`）。
后果是：将来产品前端（`apps/web`）换栈时**根本复用不到** —— 看起来集成了，其实没有。
同一轮还暴露第二个问题：只装了落地页用到的那 6 个组件，而 velora 是 100 组件 + 31 区块的完整库。

## 决策

- **组件与设计 token 只放 `apps/ui`**（`@doc-anonymizer/ui`）；任何 app 里再出现一份就是错的。
- 导入子路径：组件 `@doc-anonymizer/ui/<名字>`、区块 `/blocks/<名字>`、基础件 `/primitives/<名字>`。
- **导入规范化成相对路径**：shadcn 生成的是宿主别名 `@/…`，改成相对路径后消费方不必为 kit 配别名。
  工具 `npm run sync -w @doc-anonymizer/ui`（幂等；`check` 只检查）。
- 全量装法：`npx shadcn@latest add @velora/<名字>`（或按 `apps/ui/registry.lock.json` 批量），装完跑 `sync`。

## 证据

- 全量落地：100 组件 + 31 区块 + 9 个 shadcn 基础件，清单 `apps/ui/src/manifest.json`（131 项）。
- 守卫：`test_ui_components_live_only_in_the_shared_package`（组件只许在 `apps/ui`）、
  `test_ui_kit_ships_the_whole_library`（≥100 + ≥31、清单文件都在、导入必须已规范化）。
- 站点产物只从 1.7 M 涨到 2.3 M（未 import 的组件被 tree-shake）；根 `node_modules` 约 393 M（仅构建期）。

## 影响与代价

- 仓库多了一个 140 文件 / 948 K 的组件库，以及 npm workspaces 与仅构建期的 node 依赖。
- 换来的是：产品前端将来换栈时，改 `apps/ui` 一处，网站与产品界面一起变。
