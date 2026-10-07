# .agent/ — 给 agent（和人）看的分类规范

`AGENTS.md` 是**入口与索引**；细则按主题拆在这里，一个主题一个文件。这样做的原因很实在：
一条 160 行的大杂烩没人（也没有 agent）会读完再动手，而按主题拆开后，改前端就读前端那篇。

```
.agent/
├── README.md       ← 本文件：这套目录怎么用
├── rules/          ← 分类细则（现状权威，"是什么/不许怎样"）
├── notes/          ← 决策与修复记录（"为什么"，`{状态}/{类别}/日期-主题.md`）
├── skills/         ← 操作手册（"怎么做"，`<名字>/SKILL.md`）
├── postmortem/     ← 事故复盘（"为什么没兜住"，`NNNN-slug.md`）
（另有 `docs/cookbook/` = 场景操作指引，属 docs/ 的地盘）
    ├── 01-commands.md      命令、脚本、dev.sh 入口
    ├── 02-packages.md      Python 五包边界、引擎注册、可搬运性
    ├── 03-resources.md     资源根 / LAYOUT / 配置 / 部署契约 / 模型获取
    ├── 04-outputs.md       产物命名、账本纪律、退出码三态
    ├── 05-security.md      脱敏安全边界（PDF 栅格化、mapping.json、空串还原坑）
    ├── 06-testing.md       测试纪律与各守卫测试的分工
    ├── 07-frontend.md      前端两条契约、共享组件包、官网/文档站
    ├── 08-docs.md          文档怎么写、写在哪（一个主题一个出处）
    └── 09-environment.md   环境、可再生资产、samples、桌面壳约束
```

另外：**每个包自己有 `AGENTS.md`**（`packages/*/AGENTS.md`）写本地约束 —— DSH 这类 harness 会自动
加载 root→cwd 的 AGENTS.md 链，所以在哪个目录干活就会自动读到那一份。

## 怎么用

- **动手前**：读 `AGENTS.md` 的"六条不可违反"，再按主题表读你将要改的那一篇；
  在某个包里干活时，先看那个包的 `AGENTS.md`；要写"为什么"就去 `notes/`。
- **写完**：改行为的同步 README；改边界的同步 `AGENTS.md` 与对应 rule。
- **加一篇 rule**：主题足够大（≥ 10 行、会被反复引用）才拆；在 `AGENTS.md` 的主题表加一行——
  `tests/test_docs.py` 会检查每个 rules 文件都被 `AGENTS.md` 引用到，没人认领的规则会红。

## 硬性维护约定（都有测试）

| 约定 | 谁盯 |
|---|---|
| `AGENTS.md` 保持短（≤ 80 行），细则放 rules | `tests/test_docs.py` |
| 每篇 rule ≤ 60 行，超了就该再拆 | `tests/test_docs.py` |
| 每个 rules 文件都被 `AGENTS.md` 索引到 | `tests/test_docs.py` |
| rules 里的路径与链接必须真实存在 | `tests/test_docs.py` |
| 笔记路径必须是 `{状态}/{类别}/日期-主题.md`，且文件内 `Status:` 与目录一致 | `tests/test_docs.py` |
| 已落地的笔记必须从别处（架构表 / 规则 / README）被链到，不许有孤儿 | `tests/test_docs.py` |
| `SKILL.md` 必须自描述（`name` 与目录同名、`description` 以 `Use when ` 开头） | `tests/test_docs.py` |
| 每个 `packages/docanon-*` 都有自己的 `AGENTS.md` 且被规则索引 | `tests/test_docs.py` |
| 网站站内链接必须走 `url()`（子路径部署才不会 404） | `tests/test_docs.py` |
| 部署 workflow 必须真的跑门禁、带 SITE_BASE/SITE_URL、发 `website/dist` | `tests/test_docs.py` |
| 复盘路径必须是 `NNNN-slug.md`、首行编号一致、先给「执行摘要」、含「根因」与「护栏」，且被 README 索引 | `tests/test_docs.py` |
| 声明环境齐备(`DOCANON_REQUIRE_ENGINES=1`)后不许有任何 skip | `tests/test_dev_env.py` |
| `check_scope.py` 的建议要对（按范围选最小集） | `tests/test_check_scope.py` |

> 面向用户的说明文档在 `README.md` 与 `docs/`；这里是**面向开发者的操作契约**，两者不混。
