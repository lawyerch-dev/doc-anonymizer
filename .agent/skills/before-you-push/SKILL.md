---
name: before-you-push
description: Use when about to commit, push, or claim a change is done — to pick the smallest set of checks that actually covers the outgoing diff instead of reflexively running everything (or nothing).
---

# 推送前：按改动范围选最小检查集

本仓库没有跑测试的 CI（唯一的 CI 只部署文档站），所以"该跑什么"得自己算 —— 这两件事都别做：
无脑跑全量（慢，然后就懒得跑了），或者只跑顺手那一条（漏掉真正的风险）。

1. **先算范围**（不要凭印象）：

   ```bash
   npm run check:scope            # = python3 scripts/check_scope.py
   ```

   它把改动分成三块：committed(相对基线) / 工作区未提交 / 未跟踪，然后给出一张表命中的组、
   没有自动化覆盖的目录（`apps/web`、`apps/desktop` 要手工跑），以及无法归类的路径。

2. **跑它给出的最小集**（或直接 `npm run check:scope -- --run`）：

   | 改了 | 跑 |
   |---|---|
   | `packages/**`、`tests/**`、`configs/**`、`samples/**` | `npm run test:py` |
   | `apps/ui/**`、`website/**`、`package.json` | `npm run test:web` |
   | `docs/**`、`.agent/**`、根 markdown、`.github/**` | `pytest tests/test_docs.py -q` |
   | `scripts/**` | `pytest tests/test_dev_env.py -q` |

3. **这些情况必须全量 `npm test`**：改了 `packages/docanon-contract/`、`pyproject.toml`、
   `requirements-dev.txt`、`conftest.py`；改动**跨了多个组**；有无法归类的路径；准备发版本。

4. **装了模型/可选依赖时，用反假绿那一档**：`npm run test:strict` —— 它声明"环境齐备"，
   于是**任何 skip 都会让整轮失败**。没有它，`npm test` 全绿可能只是"引擎一次都没跑"。

5. **贴证据再说话**：把命令与输出（关键几行）写进提交信息或 PR；没跑过的别写"应该没问题"。
   详见 [`docs/cookbook/reviewing-a-change.md`](../../../docs/cookbook/reviewing-a-change.md)。
