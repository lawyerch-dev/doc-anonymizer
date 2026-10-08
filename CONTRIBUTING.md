[English](CONTRIBUTING.en.md) | 中文

# 贡献指南

## 环境

```bash
npm run setup              # 一键装齐: Python venv + 五个包(editable) + 预览资源 + npm install
```

前置：Apple Silicon macOS + Python 3.11/3.12。跑 LLM 路线要 `llama.cpp`，起桌面壳要 Hutch，
跑浏览器端 e2e 要 `npm`。缺什么用 `npm run doctor` 看。

## 常用命令

所有开发动作走仓库根的 npm scripts：`npm test`（一键全测）、`npm run test:py` / `test:web`、
`npm run dev` / `dev:website` / `dev:desktop`、`npm run cli -- …`。底层命令（排查时直接用）：

```bash
.venv/bin/python -m pytest -q                                        # 全量(约 5 秒)
.venv/bin/python -m pytest packages/docanon-core/tests/test_job.py -q # 单个文件
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml       # CLI 端到端
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml                    # 产品 Web 端到端
npm test                                                             # Python + 组件库 + 文档站构建
```

> 必须用 `.venv/bin/python -m pytest`：PATH 上的 `pytest` 可能跑在别的 Python 上（缺 `rapidocr`），
> 那样扫描件测试会被静默 skip —— OCR 回归等于没测。

仓库**没有** lint / typecheck / CI / pre-commit（理由见 [docs/architecture.md](docs/architecture.md) §七）。
所以"跑通测试 + 贴出输出"就是这里的门禁。

## 代码在哪

`packages/` 五个包（`docanon-contract` + 三个引擎包 + `docanon-core`），依赖只有一条方向：
**core → 引擎 → contract**，引擎各自可整块搬走。跨包测试在 `tests/`。

前端有两条路径：**产品运行期零 node**（`apps/web/` 零构建，`docanon web` 直接发静态文件）；
**构建期可以用 node**（npm workspaces：`packages/ui` 共享组件 + `website/` 官网/文档站，
Astro + Starlight，静态输出到 `dist/`）。

**组件只放 `packages/ui`**（`@doc-anonymizer/ui`）：网站与将来的产品前端都引它 —— 往 app 里再拷一份
velora 组件就等于复用失效（`tests/test_docs.py` 会拦）。根目录跑一次 `npm install` 即可。

## 改代码前必读

[AGENTS.md](AGENTS.md) 是入口：六条不可违反的边界 + 按主题指向 [.agent/rules/](.agent/rules/)。
引擎起不来必须报错、契约只准标准库、布局只改 `resources.LAYOUT`、产物命名与账本纪律、PDF 命中页栅格化……每条都有测试锁着。要改哪块就读那一篇 rule，别读完整本。

改完记得同步文档：`tests/test_docs.py` 会检查文档里的路径/链接/测试文件名，
**以及 `AGENTS.md` 里那句测试数量**（加删测试后要一起改，否则测试红）。

## 文档站（改了它才需要）

```bash
npm run dev:website        # 开发服务器 :4321（Astro 默认）
npm run build              # 必须能过: 静态输出到 website/dist/
```

内容来自仓库里的 markdown：加页面 = 在 `website/content-manifest.json` 加一行
（构建时 `website/scripts/sync-content.py` 生成 Starlight 要的 frontmatter，测试会检查文件存在）。
装新组件：`cd packages/ui && npx shadcn@latest add @velora/<名字>`（组件进共享包，不进城建 app）。
机制与实测坑写在 [website/README.md](website/README.md)。

## 浏览器端检查（改了预览/界面才需要）

```bash
.venv/bin/docanon web -p 8803 -c configs/onnx.yaml &
cd tests/e2e/webkit && npm install && npx playwright install webkit
DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node webkit-check.mjs   # errors 必须是 []
```

## 提交与 PR

- 分支：`feat/` `fix/` `refactor/` `docs/` …，从 `main` 开。
- 提交信息：中文，首行动词开头说做了什么，正文说为什么；一次提交只做一件事。
- PR：按模板填，重点是**贴出 `pytest -q` 的结果行**（没有 CI，人只能看这个）。

## 不做的事

不接云端 API、不依赖 Ollama、不引 lint/typecheck/CI、不做多用户与权限；PDF 命中页变位图是安全选择
不是待办。`mapping.json`、模型权重、`var/` 不要提交。

## 报问题

漏脱敏 / 敏感内容可能被还原 → [SECURITY.md](.github/SECURITY.md) 的私密渠道。
其余用 [issue 模板](.github/ISSUE_TEMPLATE/bug_report.yml)，附 `docanon engines` 输出与版本号，
**不要**附真实敏感原文。
