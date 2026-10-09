# website/ — 官网与文档站

**Astro 5 + Starlight + Tailwind 4**，组件来自共享包 [`packages/ui`](../packages/ui/README.md)（`@doc-anonymizer/ui`，velora）。
静态输出到 `dist/`，交给任意静态服务器；**运行期不需要 node**。

![搜索](https://raw.githubusercontent.com/lawyerch-dev/doc-anonymizer/main/docs/images/docs-site-search.png)

## 跑起来

```bash
npm run dev:website        # → :4321（= npm run dev -w @doc-anonymizer/website）
npm run build              # 静态输出 website/dist/
npm run preview -w @doc-anonymizer/website    # 用 python -m http.server 起 dist/
```

装依赖：仓库根 `npm run setup`（含 `npm install`；npm workspaces = `packages/ui` + `website`）。

## 内容从哪来（单一真相）

Starlight 要求内容带 frontmatter（`title` 必填），而仓库里的文档是给人读的纯 markdown。所以构建前先同步：

```
content-manifest.json              ← 唯一清单：仓库文件 → (组, slug, 标题, 说明)
  ↓ scripts/sync-content.py        ← 注入 frontmatter、把 .md 相对链接改写成站内路由
src/content/docs/<组>/<slug>.md    ← 生成物，gitignore，不要手改
src/sidebar.generated.mjs          ← 侧栏也由同一份清单生成
```

**加一页 = 在 `content-manifest.json` 加一行**（别改生成的目录，也别在 `astro.config.mjs` 里手写侧栏）。
清单里的文件不存在时同步脚本直接报错退出；`tests/test_docs.py` 也检查文件存在与 slug 不重复。

## 组件从哪来

通用组件都在 [`packages/ui`](../packages/ui/README.md)：`import { Marquee } from "@doc-anonymizer/ui/marquee";`
（内部包直接发 TS 源码，无构建步骤）。只有**页面专属**的组合组件放这里的 `src/components/`
（例如首页的 `Landing.tsx`）。加新 velora 组件：`cd packages/ui && npx shadcn@latest add @velora/<名字>`。

React 组件在 Astro 里是 island，记得带指令：`<Landing client:load />`。

## 为什么是 Astro/Starlight（实测对比）

集成时在同样条件下量过（各自独立安装的 app、同样读仓库 markdown、同样用 velora 组件）：
> 口径说明：下表体积是**探针里那个 app 自己的 node_modules**。本仓库用 workspaces 提升依赖，根 `node_modules` 约 393 M（含共享 kit 的依赖），两边的实际安装都会比这个数字大一些。

| | Astro + Starlight | Next.js（先试了一版） |
|---|---|---|
| 依赖体积 | **241 M** | 537 M |
| 构建 | **0.7 s**（整站 4 s，含搜索索引） | 3–4 s |
| 产物 | **1.2–1.8 M** | 2.0 M |
| 搜索 / TOC / 上下页 / i18n | **内置**（Pagefind 已索引 10 页 / 1672 词） | 要自己写 |
| velora 组件 | 可用（React island，实测进了静态 HTML） | 原生 |
| 读仓库外部 markdown | 可用（同步脚本 / glob loader） | 可用（构建期 fs 读） |

网站是内容站：Starlight 的现成能力省下的是天数级开发，体积与构建小一个量级；
产品前端（`apps/web`）也照样引同一个 `packages/ui`，外观不会分叉。

## 实测出来的坑

1. **Starlight 这版的 `sidebar` 不接受 `autogenerate` 写法**（类型校验直接报错）→ 侧栏改由清单生成。
2. **`.md` 链接必须改写成站内路由**（`/组/slug/`），否则页面里点过去 404；改写按清单的 slug，
   不是文件名（`README.md` → `/start/readme/`）。
3. **生成目录要让检查器跳过**：`src/content/docs/**` 是构建产物，`tests/test_docs.py` 会排除它，
   否则 CHANGELOG 里的历史名字会被误判成"现状文档里的旧名字"。
4. **Tailwind 4 要显式 `@source` 共享包**（`src/styles/global.css`），否则 kit 里的类名会被摇掉。

## 子路径部署（base）

站内链接必须走 [`src/lib/site.ts`](src/lib/site.ts) 的 `url()`：手写 `href="/…"` 只在根路径部署时成立。
`SITE_BASE` 决定 Astro 的 `base`，`SITE_URL` 决定 `site`（sitemap）。验证子路径真的成立：

```bash
SITE_BASE=/doc-anonymizer SITE_URL=https://lawyerch-dev.github.io npm run build
rm -rf /tmp/pages && mkdir -p /tmp/pages && cp -r dist /tmp/pages/doc-anonymizer
python3 -m http.server -d /tmp/pages 8080     # → http://127.0.0.1:8080/doc-anonymizer/
```

自动部署见 [`.github/workflows/deploy-website.yml`](../.github/workflows/deploy-website.yml)
（push `main` → 门禁 → 构建 → 发布 Pages）。

## 部署

```bash
SITE_BASE=/doc-anonymizer SITE_URL=https://lawyerch-dev.github.io npm run build
```

`SITE_BASE` 用于 GitHub Pages 项目页这类子路径；`SITE_URL` 供 sitemap 用（不设则跳过 sitemap 并给提示）。
`dist/` 丢给任意静态托管即可。

## 许可

页面组件来自 velora-ui（MIT），原文见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；本站与整个仓库同为 MIT。
