---
name: notes
description: Use when you need the reasoning behind a past decision or fix — why it is the way it is, what was rejected, and what evidence settled it.
---

# .agent/notes — 决策与修复记录（Agent Note）

借鉴 DeepSeek Harness 的做法：**"为什么"不塞进表格，而是写成一篇带状态的笔记**；
规则/架构表里只留一行结论 + 相对链接指过来。理由是推理细节只有笔记装得下，
而表格一挤，理由就会第一个被删。

## 路径即状态与分类（两个轴都编码在路径里）

```
.agent/notes/{lifecycle}/{class}/yyyy-mm-dd-topic-title.md
```

- **lifecycle**：`proposed/`（提案，未做或只做了一半）· `implemented/`（已落地）·
  `rejected/`（考虑过但否掉，保留到它还能拦住一个诱人的错误为止）· `archived/`（已冻结的历史快照，**不要改**）。
- **class**（封闭集合）：`feature` · `bug-fix` · `simplification` · `architecture` · `process` · `testing`。
  分类由 `tests/test_docs.py` 的门禁校验，加类要同时改门禁与本文件。
- 文件名里的日期是**首次提出**那一天；其余交给 git。

## 文件格式（门禁校验）

```markdown
# Agent Note: <标题>

Status: implemented          # 必须与所在 lifecycle 目录一致；proposed / implemented / rejected — <一句话原因>

## 问题                        # 先讲动机，能脱离方案独立成立

## 决策 / 为什么不是别的方案 / 证据（真跑过的命令与输出）/ 影响与代价
```

- 正文语言：中文（本仓库全中文；DSH 的英文+中文双份是它的规模决定的，我们不复制）。
- **被引用的笔记要保持"事实"最新**：路径、名字、默认值变了要同步改笔记（决策本身不重写）。
- **不建索引文件**（DSH 的明确规则）：索引重复了路径里的元数据，还会让互不相关的笔记改动挤在一个文件里。
  发现笔记靠目录与搜索；**从别处（架构决策表、规则、测试）用相对链接指过来**。
- 写完一篇新的，顺带查一遍有没有被它取代的旧笔记（取代了就移到 `archived/`，并在同一提交里改链接）。

## 什么时候值得写

值得：被人重新讨论过的决定、踩过一次的坑、有取舍与代价的选择、会让人重复踩的静默失效。
不值得：流水账、纯机械改动、看一眼代码就明白的事。
