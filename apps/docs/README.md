# apps/docs — 文档站

把仓库里的 markdown 变成网站，并作为 [velora-ui](https://github.com/ColorlibHQ/velora-ui)（MIT）
组件的第一个落地处：以后产品界面优化与文档站共用同一套组件与设计 token。

**Next.js 16 + Tailwind CSS 4 + Motion + shadcn/velora 组件。静态导出，运行期不需要 node。**

## 跑起来

```bash
./scripts/dev.sh docs          # = cd apps/docs && npm install(首次) && npm run dev  → :3000
cd apps/docs && npm run build  # 静态导出到 apps/docs/out/
npm run preview                # 用 python -m http.server 起 out/(零依赖)
```

## 内容从哪来

侧栏与页面都由 [`src/lib/docs.ts`](src/lib/docs.ts) 的 `DOCS` 清单驱动：`slug → 仓库里的文件`。
**改文档就是改那些 markdown 文件**（构建时读取），文档站不需要单独维护内容。
`readDoc()` 会去掉正文的一级标题（页面自己渲染标题）；`rewriteLinks()` 把 `.md` 相对链接改写成站内路由。

加一页 = 在 `DOCS` 里加一行，指向仓库里已有的 `.md`。测试会检查清单里的文件真的存在。

## 加 velora 组件

registry 已在 [`components.json`](components.json) 里注册，直接按名字装（组件源码会落到
`src/components/velora/`，随仓库提交 —— 这是 shadcn 的模式，便于按需改）：

```bash
cd apps/docs
npx shadcn@latest add @velora/marquee       # 100 个组件任选, 名字见 velora.colorlib.com/components
npx shadcn@latest add https://velora.colorlib.com/r/hero-globe.json   # blocks 用完整 URL
```

已装：`marquee` `blur-fade` `number-ticker` `globe`（+ `ui/button`）与 `hero-globe` block。

## 三个实测出来的坑

1. **别开 `cacheComponents` / PPR**：Next 16 的模板默认开着，与 `output: "export"` 不兼容，
   构建会以 `Invariant: PPR cannot be enabled in export mode` 直接失败（`next.config.ts` 里有注释）。
2. **`trailingSlash: true`**：输出 `out/docs/quickstart/index.html` 这种目录式文件(构建产物, 不提交)，
   任何静态服务器（含 `python -m http.server`、GitHub Pages）都能直接访问，不依赖"省略扩展名"规则。
3. **字体走系统栈**：不用 `next/font/google`，否则构建要联网（本项目的运行期与构建都尽量离线）。

部署到子路径（如 GitHub Pages 项目页）：
`NEXT_PUBLIC_BASE_PATH=/doc-anonymizer npm run build`。

## 许可

组件来自 velora-ui（**MIT**，© Colorlib），本仓库同样 MIT；`src/components/velora/**` 与
`src/components/blocks/hero-globe.tsx` 保留其原始内容与注释，改动它们时注意别丢版权头。
