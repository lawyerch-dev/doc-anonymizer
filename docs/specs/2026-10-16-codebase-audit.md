# 全仓梳理报告（2026-10-16）

> **这不是实现设计，是一次体检的记录 + 待办清单。** 现状仍以 [README](../../README.md)、
> [AGENTS.md](../../AGENTS.md)、[docs/architecture.md](../architecture.md) 为准。
>
> 背景：本项目由多个 AI 分头开发，怀疑存在「文档过时/重复」「同一件事实现两遍」「没按更简洁的方式实现」。
> 本次先跑机械守卫拿基线，再派三路只读侦察把守卫**抓不到**的语义层问题捞出来。逐条都带证据（`文件:行号`），
> 动手前需各自复核。
>
> **进展（2026-10-16 收尾）**：文档红线与口径、Python 的 P-1~P-5、前端的 F-1~F-5 均已修（见 `git log`）；
> 只有 **P-6**（`Block.locator`/`meta` 类型化，跨包契约变更）留作未决，记为
> [`.agent/notes/proposed/architecture/2026-10-16-typed-locator-meta.md`](../../.agent/notes/proposed/architecture/2026-10-16-typed-locator-meta.md)。


## 方法

1. `npm run doctor` + `npm test` 拿基线——机械守卫（[tests/test_docs.py](../../tests/test_docs.py)、
   [tests/test_architecture.py](../../tests/test_architecture.py)、[tests/test_engine_portability.py](../../tests/test_engine_portability.py)）
   覆盖的「旧路径/旧名字/双语哈希/链接/测试数量/单一出处/组件拷贝/包边界」当时全绿。
2. 三路只读侦察并行：Python 侧、前端侧、文档↔代码一致性。**只看不改**，产出候选 + 严重度。

## 已做的修复（文档类，另见提交）

文档↔代码的语义漂移（守卫抓不到的那类）——共 6 处 🔴/🟠 与 7 处 🟡，已修，见 `git log` 的
`docs: 修正文档与代码不符的红线` 与 `docs: 统一口径类小漂移`。要点：`restore` 支持格式、
`legal.yaml` 不是 CLI 默认、onnx 默认是锚点非 `**`、「仓库没有 CI」的断言、接口清单缺项、
README.en 缺还原 API 段。

## 一、Python 侧：重复实现 / 浅模块（待办）

| # | 严重度 | 问题 | 证据 |
|---|---|---|---|
| P-1 | 🔴 | restore 单份 vs 批量的三道安全闸（token / `_safe_join` / 体积）逐行重复 | `packages/docanon-core/src/docanon_core/server/routes.py` 单份约 :795-876、批量约 :878-993 |
| P-2 | 🔴 | span 偏移的正/逆算法两处，靠注释维系一致；错位=漏脱敏+损坏 | `packages/docanon-core/src/docanon_core/redaction/writers.py` 约 :49-84 与 `redaction/restorers.py` 约 :215-248 |
| P-3 | 🔴 | `downloads` ↔ `prepare`：目录校验 + `_Job` + 可续传下载三重复制，schema 已分叉 | `server/downloads.py` 约 :39/:106/:172 与 `server/prepare.py` 约 :69/:190/:350 |
| P-4 | 🔴 | `mapping.json`（含原文的半本账）用裸 `write_text` 非原子写，`manifest.json` 却是原子写 | `redaction/mapping.py` 约 :84 与 `job.py` 约 :85 |
| P-5 | 🟠 | 命名协议 `_restored_name` 两处；锚点语法散落 4 处 | `routes.py` 约 :87 与 `cli.py` 约 :188；`redaction/strategies.py` 约 :75 与 `redaction/restorers.py` 约 :23 |
| P-6 | 🟠 | `locator`/`meta` 是无类型 dict，引擎↔core 靠私有键耦合，AST 守卫抓不到 | `docanon_contract/contract.py` 约 :22/:41/:52 |

## 二、前端侧：重复实现 / App 过重（待办）

| # | 严重度 | 问题 | 证据 |
|---|---|---|---|
| F-1 | 🟠 | DocStatus 词汇表写三遍（标签 + 颜色 + 筛选 + 占位文案） | `apps/web/src/components/PresetList.tsx` 约 :10-41、`apps/web/src/App.tsx` 约 :636-646 |
| F-2 | 🔴 | run / runBatch 整套生命周期近复制（含轮询/取消/错误映射，零测试） | `apps/web/src/App.tsx` 约 :504-571 与 :573-610 |
| F-3 | 🟠 | 配置自动保存 9 state + 8 handler 全堆在根，可抽 hook | `apps/web/src/App.tsx` 约 :224-306 |
| F-4 | 🟠 | `pickFolder` 约 100 行纯逻辑（四类计数 + notes）可抽纯函数单测 | `apps/web/src/App.tsx` 约 :381-483 |
| F-5 | 🟡 | 上限常量与文案脱钩；job id 生成 3 份；取扩展名 4 份 | `apps/web/src/App.tsx` 约 :36/:445/:57 等 |

**前端硬约束（不可动）**：[`.agent/rules/07-frontend.md`](../../.agent/rules/07-frontend.md) 列出的 E2E 钩子
—— `#loadSamples` `.preset` `#run` `#cancelRun` `#pickFolder` `.doc-row`(`data-status`) `#batchSummary`
`#downloadZip` `#editUploadRule` `#stats` `#paneSrc` `#paneOut` `#progress`。
另有一份更大的三栏改造计划（`.trae/documents/lawredact-workbench-layout.md`）多数未落地，
动 `App.tsx` 前需与它对齐，尤其 `#stats`/`#pickFolder` 的挂载位置。

## 三、建议顺序

1. **文档红线**（✅ 已完成）。
2. **F-1**：零 DOM 风险，先做，可顺手简化 `outPlaceholder` 的三元链。
3. **P-1**：安全敏感但集中在一个文件，收敛成「batch of 1」，配测试。
4. **P-2 / P-4**：爆炸半径最大（漏脱敏 + 半截账本），同样配测试。
5. **F-2 / F-3 / F-4**、**P-3 / P-5 / P-6**：按需排期。
6. **`/retro`**：把这次发现的漂移做成新守卫（如 README 的 restore 支持格式必须等于
   `restorers` 的路由表；现状文档里 `legal.yaml` 不许再被写成 CLI 默认），防止下一个 AI 再犯。

## 四、守卫覆盖 vs 未覆盖（本次结论）

- **已机械锁住**：路径/旧名字/双语哈希/链接/测试数量/单一出处（4 主题）/组件拷贝/包边界/引擎可搬运/
  笔记与复盘格式。
- **锁不住、要靠人读**：行为描述是否过时（本次修的 6 处红线的类型）、跨模块重复实现、
  模块深浅与 seam。
