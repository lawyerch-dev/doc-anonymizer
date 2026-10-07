# 文档怎么写、写在哪

**一个主题只有一个出处**，其余用链接——冗余是文档互相矛盾的起点。
`tests/test_docs.py` 的 `test_each_topic_has_one_owner` 盯几条最容易被复述的内容（目录树、已知限制、
硬边界表、一键命令清单）。

| 谁 | 管什么 | 权威性 |
|---|---|---|
| `README.md` | 产品门面与唯一使用手册：定位、命令、产物、配置、引擎、已知限制、导航 | 现状权威 |
| `docs/quickstart.md` | 第一次跑通 + 常见问题 | 现状权威 |
| `AGENTS.md` | **入口与索引**：不可违反的边界、命令速查、按主题指向 `.agent/rules/` | 现状权威 |
| `.agent/rules/*.md` | 分类细则（命令/包/资源/产物/安全/测试/前端/文档/环境） | 现状权威 |
| `.agent/notes/**` | 决策与修复记录：`{状态}/{类别}/日期-主题.md`，格式与生命周期见其中的 README | 记录类（允许旧名字） |
| `.agent/skills/*/SKILL.md` | 操作手册：加检测器 / 加引擎包 / 发版本 | 现状权威 |
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
