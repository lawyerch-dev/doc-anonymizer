# doc-anonymizer 操作契约（入口）

本地文档脱敏：中文优先、全离线、保留原格式。Python 五个包（`packages/`）+ 零构建产品前端
（`apps/web/`）+ 共享 React 组件包（`apps/ui/`）+ Astro 官网/文档站（`website/`）。

**这里是入口与索引**：细则按主题拆在 [`.agent/rules/`](.agent/rules/)，改哪块读哪篇
（[`.agent/README.md`](.agent/README.md) 说明这套目录怎么用）。

## 开发入口

```bash
./scripts/dev.sh setup      # 幂等: venv + 五个包 + 预览资源 + 字节码缓存重定向
./scripts/dev.sh web        # 产品界面 → :8000
./scripts/dev.sh website    # 官网/文档站 → :4321
./scripts/dev.sh desktop    # 桌面壳（需 Hutch）
./scripts/dev.sh test       # 全量测试（114 项，约 5 秒）
```

其余子命令：`cli` / `engines` / `models` / `doctor`（`./scripts/dev.sh help` 看全部）。
命令与脚本细则 → [`01-commands.md`](.agent/rules/01-commands.md)。

## 六条不可违反（都有测试锁着）

| # | 边界 | 细则 |
|---|---|---|
| 1 | **少一层必须报错**：引擎起不来就退出（连输出目录都不建），不许静默给空结果 | [02](.agent/rules/02-packages.md) · [05](.agent/rules/05-security.md) |
| 2 | **包边界**：契约只准标准库；引擎只依赖契约+自己；core 只用引擎公开面 | [02](.agent/rules/02-packages.md) |
| 3 | **资源与布局只有一处真相**（`resources.LAYOUT` + 资源根验证，读不到就报错） | [03](.agent/rules/03-resources.md) |
| 4 | **产物命名与账本纪律不许改**（每文件原子落盘；`--resume` 要求产物仍在） | [04](.agent/rules/04-outputs.md) |
| 5 | **命中敏感信息的 PDF 页整页栅格化**（不许留可复制的文字层） | [05](.agent/rules/05-security.md) |
| 6 | **文档与代码不许漂移**（路径/链接/测试数量/组件复用都有守卫） | [06](.agent/rules/06-testing.md) · [08](.agent/rules/08-docs.md) |

## 按主题找细则

| 我要改 / 想知道 | 读 |
|---|---|
| 命令、脚本、dev.sh 入口 | [`01-commands.md`](.agent/rules/01-commands.md) |
| Python 包边界、引擎注册、可搬运性 | [`02-packages.md`](.agent/rules/02-packages.md) |
| 资源根、配置、部署契约、模型获取 | [`03-resources.md`](.agent/rules/03-resources.md) |
| 产物命名、账本、退出码 | [`04-outputs.md`](.agent/rules/04-outputs.md) |
| 脱敏安全边界 | [`05-security.md`](.agent/rules/05-security.md) |
| 测试纪律与守卫分工 | [`06-testing.md`](.agent/rules/06-testing.md) |
| 前端（apps/ui · website · apps/web） | [`07-frontend.md`](.agent/rules/07-frontend.md) |
| 文档怎么写、写在哪 | [`08-docs.md`](.agent/rules/08-docs.md) |
| 环境、可再生资产、samples、桌面壳 | [`09-environment.md`](.agent/rules/09-environment.md) |

## 三条纪律

- 改行为 → 同步 README 与对应 rules；改边界 → 改本文件与对应 rule。
- 写进文档的每条命令都要**真跑一遍**再说它成立，不许写"理论上"。
- 能力边界（哪些引擎认识哪些实体、起不起得来）不要写死进文档，让 `docanon engines` 自己报。
