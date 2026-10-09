# 前端（产品界面 · 共享组件 · 官网）

**两条契约，别搞混**：

1. **产品运行期零 node、全离线**：`docanon web` 只发静态文件（`apps/web/dist/`，
   由 Vite 从 `apps/web/src/` 构建；**运行期不发 node**，构建期用 npm workspaces）。
2. **构建期可以用 node**：npm workspaces（仓库根跑一次 `npm install`）。

| 目录 | 是什么 |
|---|---|
| `packages/ui/` | `@doc-anonymizer/ui`：**共享组件库** —— velora 100 个组件 + 31 个区块 + 9 个 shadcn 基础件 + 设计 token，只有这一份 |
| `website/` | 官网 + 文档站：Astro 5 + Starlight + Tailwind 4，静态输出 `website/dist/` |
| `apps/web/` | 产品界面：Vite + React + Tailwind 4，引同一个 `packages/ui`；产物 `dist/` |

- **别把 velora 组件拷进任何 app**：复用靠包不靠复制，`tests/test_docs.py` 会拦
  （为什么：[决策记录](../notes/implemented/architecture/2026-10-07-shared-ui-package.md)）。
  导入方式：组件 `@doc-anonymizer/ui/<名字>`、区块 `@doc-anonymizer/ui/blocks/<名字>`、
  基础件 `@doc-anonymizer/ui/primitives/<名字>`。名录见 `packages/ui/src/manifest.json`
  （文档站「开发 → 组件库总览」就是它渲染的）。
- 加组件：`cd packages/ui && npx shadcn@latest add @velora/<名字> && npm run sync -w @doc-anonymizer/ui`
  —— `sync` 把 shadcn 的 `@/` 导入改成相对路径并刷新清单（守卫会检查有没有漏改的）。
- 页面专属的组合组件放各自的 `src/components/`（如 `website/src/components/Landing.tsx`）。
- website 的内容：`website/content-manifest.json`（唯一清单）→ `website/scripts/sync-content.py`
  生成 `src/content/docs/**` 与侧栏（生成物 gitignore，**源始终是仓库里的 markdown**）。
  加一页 = 清单加一行，别改生成目录，也别在 `astro.config.mjs` 里手写侧栏。
- Tailwind 4 要显式 `@source` 共享包源码（`website/src/styles/global.css`），否则 kit 的类名被摇掉
  （踩过：搬家后路径少一层，`sr-only`/aurora/渐变静默失效 —— [复盘](../postmortem/0001-tailwind-source-dropped-classes.md)）。
- React 组件在 Astro 里是 island：`<Landing client:load />`。
- 部署：`SITE_BASE=/doc-anonymizer SITE_URL=https://… npm run build`（`SITE_BASE` → Astro `base`，
  `SITE_URL` → `site`/sitemap）。**子路径部署时手写 `href="/…"` 会 404** —— 站内链接一律走
  `website/src/lib/site.ts` 的 `url()`（守卫会拦）；Starlight 自生成的链接跟着 `base` 走。
- 唯一的 CI 就是[部署文档站](../../.github/workflows/deploy-website.yml)：先跑门禁再发布 Pages。
  详细步骤（含子路径预览的验证方法）见 [`docs/cookbook/shipping-the-website.md`](../../docs/cookbook/shipping-the-website.md)。
- **DOM 契约**：`tests/e2e/webkit/` 按 `.preset` `#run` `#paneSrc` `#paneOut` `#stats` 选择元素 ——
  改界面时这几个钩子（`#paneSrc`/`#paneOut` 的 `firstElementChild` 是预览挂载点）不许改名或挪位置。
- 加前端依赖/改构建：`npm run build:web`；dev 态 `npm run dev`（后端 + Vite 并发 + 五条前缀代理），
  生产形态 `npm run build:web && npm run dev:backend`。

## Web 配置面（分层脱敏口径）

`docanon web` 的"口径"不是选一个 yaml，而是**三层渐进披露**：L1 口径（内置预设只读 / 我的配置）→
L2 逐类型策略 + 词典 → L3 检测器/模型。校验与落盘集中在
`packages/docanon-core/src/docanon_core/server/profiles.py`（纯函数 + 文件读写），`routes.py` 只做 HTTP 胶水。

- **内置只读**：`configs/*.yaml` 只能读；用户配置写 `var/configs/<name>.yaml`（与内置**同 schema**，
  复用 `load_config`），名字 `^[A-Za-z0-9_-]{1,32}$`（不含点 → 不与内置撞名、杜绝穿越），**原子写**。
- **内联试跑**：`/api/anonymize` 的 `config` 可为配置名（旧行为）或**内联对象**；改完即测，满意再保存/导出。
- **预检语义**：列表接口**不**预检；**运行**时 `prepare_detectors` 预检，缺引擎/模型返回 **400 + 原因**，
  绝不静默少一层。保存只做结构校验（换台机器/后补模型仍可用）。
- 不暴露 OCR、产物命名等"静默少一层"或属契约（非偏好）的选项。
- 为什么用户配置放 `var/`、为什么 L1 是模板：[决策记录](../notes/implemented/feature/2026-10-08-web-redaction-config.md)。
