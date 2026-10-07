# apps/ui — 共享 UI 组件（`@doc-anonymizer/ui`）

**这是复用的关键**：velora 组件与设计 token 只放这里一份，`website/` 现在引它，
**将来产品前端（`apps/web`）换栈时也引它** —— 换框架不会换外观。

- 组件：`marquee` `blur-fade` `number-ticker` `globe` `button` `hero-globe`，来自
  [velora-ui](https://github.com/ColorlibHQ/velora-ui)（MIT，见 [THIRD_PARTY_NOTICES](../../website/THIRD_PARTY_NOTICES.md)）。
- 设计 token：[`src/theme.css`](src/theme.css)（shadcn 变量）。消费方在 globals.css 里
  `@import "@doc-anonymizer/ui/theme.css";` 并 `@source "../../ui/src";`（Tailwind 4 要扫到这里的类名）。
- 没有构建步骤：`exports` 直接指向 `.tsx` 源码，由消费方的打包器编译（内部包的标准做法）。
- 加组件：`cd apps/ui && npx shadcn@latest add @velora/<名字>`，再把 `@/lib/utils` 改成 `./utils`。

装依赖在**仓库根**跑一次 `npm install` 即可（npm workspaces 会装好 ui 与 website）。
