# packages/ui — 共享组件库（`@doc-anonymizer/ui`）

**这是复用的关键**：组件与设计 token 只放这一份，`website/` 与产品前端（`apps/web`）都引它
—— 换框架不会换外观。

## 里面有什么

| 目录 | 数量 | 导入方式 |
|---|---|---|
| `src/components/velora/` | **100** 个 [velora-ui](https://github.com/ColorlibHQ/velora-ui) 组件 | `@doc-anonymizer/ui/marquee` |
| `src/components/blocks/` | **31** 个 velora 区块（hero/feature/pricing/faq/footer…） | `@doc-anonymizer/ui/blocks/hero-globe` |
| `src/components/ui/` | 10 个 shadcn 基础件（button/input/label/sheet/dialog…） | `@doc-anonymizer/ui/primitives/button` |
| `src/theme.css` | 设计 token + 全部 keyframes（消费方 `@import` 即可） | `@import "@doc-anonymizer/ui/theme.css";` |
| `src/manifest.json` | 上面这些的清单（网站"组件库总览"页就是它渲染的） | `@doc-anonymizer/ui/manifest.json` |

完整名录（131 项、带说明）：文档站 →「开发 → 组件库总览」，或直接看
[`src/manifest.json`](src/manifest.json)。

## 用法

```tsx
import { Marquee } from "@doc-anonymizer/ui/marquee";
import { HeroGlobe } from "@doc-anonymizer/ui/blocks/hero-globe";
import { Button } from "@doc-anonymizer/ui/primitives/button";
```

- **没有构建步骤**：`exports` 直接指向 `.tsx` 源码，由消费方的打包器编译（内部包的标准做法）。
- 消费方在 globals.css 里：`@import "@doc-anonymizer/ui/theme.css";` + `@source` 到 kit 的源码
  （Tailwind 4 要扫得到，否则类名被摇掉——踩过：`website` 搬家后路径没改，`sr-only` 与
  `bg-brand-*` 全失效）。
- Astro 里是 island：`<Landing client:load />`。
- 依赖：`motion`（47 个组件用）、`lucide-react`、`@base-ui/react`、`class-variance-authority`、`cn`、
  `tw-animate-css`；React 是 peerDependency。**没有 next/\* 依赖**，所以 Astro/Vite 里同样能用。

## 维护

```bash
cd packages/ui
npm run sync        # 规范化导入(@/ → 相对路径) + 从 registry.lock.json 重新生成 manifest
npm run check       # 只检查不写(测试用): 有未规范化的导入就退出 1
npx shadcn@latest add @velora/<名字>    # 加单个组件(装完记得 npm run sync)
```

- 全量重装：`npx shadcn@latest add $(sed 's|^|@velora/|' /tmp/names)`，或从
  [`registry.lock.json`](registry.lock.json) 里取名字（那份快照是 131 项的源头，提交在仓库里）。
- **导入必须是相对路径**：`@/` 是 shadcn 的宿主别名，消费方不该为 kit 配别名
  （`tests/test_docs.py` 会检查）。
- 组件源码保留上游内容与注释；许可见 [`website/THIRD_PARTY_NOTICES.md`](../../website/THIRD_PARTY_NOTICES.md)（MIT，© Colorlib）。
