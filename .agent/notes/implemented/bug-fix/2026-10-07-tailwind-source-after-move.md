# Agent Note: 搬家后 Tailwind `@source` 失效：类名被静默摇掉

Status: implemented

## 问题（三个看起来无关的现象）

1. 数字组件显示成双份：`4` → `44`、`34ms` → `3434ms`、`0` → `00`；
2. `aurora-background` 背景全透明；
3. `animated-gradient-text` 是纯色，没有渐变。

## 根因（一个）

`website/` 从 `apps/website/` 搬到仓库根后，`website/src/styles/global.css` 里的
`@source "../../apps/ui/src"` **少了一层**，指向不存在的目录。
Tailwind 对不存在的 `@source` **不报错**，只是扫不到 `apps/ui` 里的类名 → 静默摇掉：

- `sr-only` 没了 → 组件的屏幕阅读器文本可见（"双份"的来源）；
- `bg-brand-*` / `animate-aurora-*` 没了 → 光晕无颜色、无动画；
- 渐变工具的类同理。

## 决策

修正为 `@source "../../../apps/ui/src";`，并**为这类静默失效加门禁**：
`tests/test_docs.py::test_tailwind_sources_resolve` 要求每个 `@source` 指向真实存在的目录。

## 证据（浏览器实测计算样式，不是猜）

```
sr-only      → position: absolute; width: 1px; clip: inset(50%)
aurora blob  → background-color: oklch(0.546 0.245 263); animation-name: aurora-1
gradient text→ background-image: linear-gradient(to right, oklch(0.546 …) …)
```

## 教训

静默失效的配置最贵：**能被检查的就写成检查**。这条从"看着是三个 bug"到"一个根因"，
靠的是浏览器里的计算样式，所以把这种证据形态留在这里。
