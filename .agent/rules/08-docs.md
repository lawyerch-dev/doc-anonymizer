# 文档怎么写、写在哪

**一个主题只有一个出处**，其余用链接——冗余是文档互相矛盾的起点。
`tests/test_docs.py` 的 `test_each_topic_has_one_owner` 盯几条最容易被复述的内容（目录树、已知限制、
硬边界表、一键命令清单）。

| 谁 | 管什么 | 权威性 |
|---|---|---|
| `README.md` | 产品门面与唯一使用手册：定位、命令、产物、配置、引擎、已知限制、导航 | 现状权威 |
| `docs/AGENTS.md` | `docs/` 的本地约定（教程 vs 参考、事实只有一个出处、不在这里放规则） | 现状权威 |
| `docs/quickstart.md` | 第一次跑通 + 常见问题 | 现状权威 |
| `docs/cookbook/*.md` | 场景操作指引：评审改动 / 排查问题 / 构建部署网站（每步带验证） | 现状权威 |
| `AGENTS.md` | **入口与索引**：不可违反的边界、命令速查、按主题指向 `.agent/rules/` | 现状权威 |
| `.agent/rules/*.md` | 分类细则（命令/包/资源/产物/安全/测试/前端/文档/环境） | 现状权威 |
| `.agent/notes/**` | 决策与修复记录：`{状态}/{类别}/日期-主题.md`，格式与生命周期见其中的 README | 记录类（允许旧名字） |
| `.agent/skills/*/SKILL.md` | 操作手册：加检测器 / 加引擎包 / 发版本 / 推送前检查 | 现状权威 |
| `.agent/postmortem/NNNN-*.md` | 事故复盘：漏到线上的 bug 的机制、为什么没兜住、补了什么护栏 | 记录类 |
| `packages/*/AGENTS.md` | 每个包本地的约束（harness 自动按目录加载） | 现状权威 |
| `CONTRIBUTING.md` | 参与开发：环境、测试、提交与 PR | 现状权威 |
| `docs/architecture.md` | 目录与分层的**为什么**、硬边界索引、决策记录、搬迁历史 | 解释性 |
| `docs/benchmarks.md` | 模型选型与基准数字 | 实测记录 |
| `.github/SECURITY.md` | 安全问题的报告流程与已有边界 | 现状权威 |
| `CHANGELOG.md` · `docs/specs/*` | **记录类**：允许出现旧名字与旧路径 | 历史 |

- 改行为 → 同步 README 与对应 rules；改边界 → 改 `AGENTS.md` 与对应 rule。
- **写进文档的每条命令都要真跑一遍**再说它成立，不许写"理论上"。
- **能力边界不要手写进文档**（哪些引擎认识哪些实体、起不起得来），让 `docanon engines` 自己报 ——
  写死的清单一定会漂移。
- docs 站的内容来自仓库 markdown（清单在 `website/content-manifest.json`），不要另存一份。

## 双语文档（中英必须成对）

- **产品层文档必须有英文版**：`README.md`、`docs/quickstart.md`、`docs/architecture.md`、
  `CONTRIBUTING.md` 各有 `<名字>.en.md` 孪生文件。开发内部文档（契约细则/决策记录/操作手册/事故复盘/包说明）
  目前**仅中文**，英文站对它们用中文内容回退（不 404）。
- **改中文就必须改英文**：门禁 `test_bilingual_pages_are_paired_and_fresh` 比对"译文基线哈希"
  （`website/content-manifest.json` 的 `en_hash` = 翻译时中文源的 sha256 前 16 位）。中文一改就红，
  提醒你更新译文并跑 `python3 website/scripts/sync-content.py --record-hashes`。
- 两份文件顶部要有互相切换的行（中文侧 `[English](x.en.md) | 中文`，英文侧 `English | [中文](x.md)`）；
  站点生成时这行会被去掉（Starlight 自带语言切换器）。
- 步骤见 [`docs/cookbook/maintaining-bilingual-docs.md`](../../docs/cookbook/maintaining-bilingual-docs.md)。

