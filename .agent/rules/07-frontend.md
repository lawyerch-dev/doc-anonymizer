# 前端（产品界面 · 共享组件 · 官网）

**两条契约，别搞混**：

1. **产品运行期零 node、全离线**：`docanon web` 只发静态文件（现在是零构建的 `apps/web/`：
   `index.html` + `app.css` + `app.js`）。
2. **构建期可以用 node**：npm workspaces（仓库根跑一次 `npm install`）。

| 目录 | 是什么 |
|---|---|
| `apps/ui/` | `@doc-anonymizer/ui`：**共享组件库** —— velora 100 个组件 + 31 个区块 + 9 个 shadcn 基础件 + 设计 token，只有这一份 |
| `website/` | 官网 + 文档站：Astro 5 + Starlight + Tailwind 4，静态输出 `website/dist/` |
| `apps/web/` | 产品界面（零构建；将来换栈时引同一个 `apps/ui`） |

- **别把 velora 组件拷进任何 app**：复用靠包不靠复制，`tests/test_docs.py` 会拦
  （为什么：[决策记录](../notes/implemented/architecture/2026-10-07-shared-ui-package.md)）。
  导入方式：组件 `@doc-anonymizer/ui/<名字>`、区块 `@doc-anonymizer/ui/blocks/<名字>`、
  基础件 `@doc-anonymizer/ui/primitives/<名字>`。名录见 `apps/ui/src/manifest.json`
  （文档站「开发 → 组件库总览」就是它渲染的）。
- 加组件：`cd apps/ui && npx shadcn@latest add @velora/<名字> && npm run sync -w @doc-anonymizer/ui`
  —— `sync` 把 shadcn 的 `@/` 导入改成相对路径并刷新清单（守卫会检查有没有漏改的）。
- 页面专属的组合组件放各自的 `src/components/`（如 `website/src/components/Landing.tsx`）。
- website 的内容：`website/content-manifest.json`（唯一清单）→ `website/scripts/sync-content.py`
  生成 `src/content/docs/**` 与侧栏（生成物 gitignore，**源始终是仓库里的 markdown**）。
  加一页 = 清单加一行，别改生成目录，也别在 `astro.config.mjs` 里手写侧栏。
- Tailwind 4 要显式 `@source` 共享包源码（`website/src/styles/global.css`），否则 kit 的类名被摇掉
  （踩过：搬家后路径少一层，`sr-only`/aurora/渐变静默失效 —— [复盘](../notes/implemented/bug-fix/2026-10-07-tailwind-source-after-move.md)）。
- React 组件在 Astro 里是 island：`<Landing client:load />`。
- 部署：`SITE_BASE=/doc-anonymizer SITE_URL=https://… npm run build`（`SITE_BASE` → Astro `base`，
  `SITE_URL` → `site`/sitemap）。**子路径部署时手写 `href="/…"` 会 404** —— 站内链接一律走
  `website/src/lib/site.ts` 的 `url()`（守卫会拦）；Starlight 自生成的链接跟着 `base` 走。
- 唯一的 CI 就是[部署文档站](../../.github/workflows/deploy-website.yml)：先跑门禁再发布 Pages。
  详细步骤（含子路径预览的验证方法）见 [`docs/cookbook/shipping-the-website.md`](../../docs/cookbook/shipping-the-website.md)。
