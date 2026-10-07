# AGENTS.md — docs/ 本地约定

这里放**面向人的说明与历史**：`quickstart.md`（跟着走到结果）、`architecture.md`（查结构与决策）、
`benchmarks.md`、`specs/`（当时的完整设计）、`cookbook/`（带编号验证步骤的操作指引）。

- **不在这里放规则**（规则在 [`.agent/rules/`](../.agent/rules/)）；**不在这里写"为什么"的长篇**
  （决策与踩坑在 [`.agent/notes/`](../.agent/notes/README.md)）。这里是"现状与怎么做"。
- **每条事实只有一个出处**：别处要用就链接过来，不要抄第二份（`tests/test_docs.py` 会拦）。
- 分清**教程**（有序走到一个结果，只讲这一步需要的）与**参考**（查具体行为，不排教学顺序）。
- `cookbook/` 里每一步都必须是**真跑过**的命令，并给出"怎么知道对了"。
- 改产品行为 → 同步 `README.md` 与 `docs/quickstart.md`；改边界 → 改 `.agent/rules/` 与根 `AGENTS.md`。
