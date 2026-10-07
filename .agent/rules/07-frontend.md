# 前端（产品界面 · 共享组件 · 官网）

**两条契约，别搞混**：

1. **产品运行期零 node、全离线**：`docanon web` 只发静态文件（现在是零构建的 `apps/web/`：
   `index.html` + `app.css` + `app.js`）。
2. **构建期可以用 node**：npm workspaces（仓库根跑一次 `npm install`）。

| 目录 | 是什么 |
|---|---|
| `apps/ui/` | `@doc-anonymizer/ui`：**共享组件包**，velora 组件（MIT）+ 设计 token `theme.css`，只有这一份 |
| `website/` | 官网 + 文档站：Astro 5 + Starlight + Tailwind 4，静态输出 `website/dist/` |
| `apps/web/` | 产品界面（零构建；将来换栈时引同一个 `apps/ui`） |

- **别把 velora 组件拷进任何 app**：复用靠包不靠复制，`tests/test_docs.py` 会拦。
  加组件：`cd apps/ui && npx shadcn@latest add @velora/<名字>`。
- 页面专属的组合组件放各自的 `src/components/`（如 `website/src/components/Landing.tsx`）。
- website 的内容：`website/content-manifest.json`（唯一清单）→ `website/scripts/sync-content.py`
  生成 `src/content/docs/**` 与侧栏（生成物 gitignore，**源始终是仓库里的 markdown**）。
  加一页 = 清单加一行，别改生成目录，也别在 `astro.config.mjs` 里手写侧栏。
- Tailwind 4 要显式 `@source` 共享包源码（`website/src/styles/global.css`），否则 kit 的类名被摇掉。
- React 组件在 Astro 里是 island：`<Landing client:load />`。
- 部署：`SITE_BASE=/doc-anonymizer SITE_URL=https://… npm run build -w @doc-anonymizer/website`。
