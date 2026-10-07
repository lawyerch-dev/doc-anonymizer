---
name: postmortem
description: Use when a bug escaped the nets — write a postmortem; or when you want to know why a past failure class happened and what guardrail now stops it.
---

# .agent/postmortem — 事故复盘

**和 [`.agent/notes/`](../notes/README.md) 分工不同**：笔记写"我们决定这么做，放弃了什么"（这是**决策**）；
复盘写"这个东西漏到了不该到的地方，**为什么我们的网没兜住**，加了什么护栏"（这是**失败**）。
一个 bug 值得复盘，三个条件都要满足（借鉴 DeepSeek Harness）：

- **隐蔽**：机制不直观，一个仔细的人也要花时间才能重新推一遍；
- **系统性**：它漏过去的原因是测试/工具/约定的缺口，不是一次手滑；
- **重学成本高**：当时真的花了调试时间，再来一次还会花。

只满足一条的，写进 `notes/implemented/bug-fix/` 就够了。

## 格式（门禁校验）

```
.agent/postmortem/NNNN-slug.md        # 四位编号, 从 0001 起, 不复用
```

```markdown
# 事故复盘 NNNN：<一句话标题>

## 执行摘要
三十秒能读完：坏了什么 / 根因（人话）/ 为什么漏过去 / 留下的教训。

## 影响
影响面与严重度（谁受影响、能不能恢复、有没有数据损失）。

## 时间线
什么时候引入、什么时候发现、什么时候修好 —— 只写有证据的节点。

## 根因
机制层面讲清"为什么必然会这样"，不是"我改错了哪一行"。

## 为什么没兜住
逐条列出本该拦住它的网（测试/守卫/评审/文档），以及**每张网为什么失效**。

## 护栏
这次补上的检查（测试/规则/守卫），并链接到它们；写清它拦的是哪一类问题。

## 如果重来
下次怎么更早发现（可执行的信号，不是"更小心"）。
```

## 现有复盘

| # | 标题 |
|---|---|
| [0001](0001-tailwind-source-dropped-classes.md) | 搬家改了路径，Tailwind 类名被静默摇掉（数字双份 / 光晕透明 / 渐变失效） |
