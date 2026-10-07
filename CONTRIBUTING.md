# 贡献指南

先谢过愿意花时间的人。这份文档讲**怎么把环境跑起来、怎么改、改完怎么证明没坏**。
读完它能省下你翻代码的时间；改代码前请再读一遍 [AGENTS.md](AGENTS.md)（不可违反的边界都在那）。

## 1. 开发环境

```bash
git clone https://github.com/lawyerch/doc-anonymizer && cd doc-anonymizer
./scripts/setup_dev.sh
```

它做三件事：建 `.venv`、把 `packages/` 下五个包按 editable 装好（外加测试依赖）、把字节码缓存
重定向到 `var/pycache`（所以源码树里不会到处是 `__pycache__`）。幂等，随时可重跑。

前置：Apple Silicon macOS + Python 3.11/3.12。跑 LLM 路线额外需要 `llama.cpp`；
跑浏览器端 e2e 需要 `npm`（见第 5 节）。

## 2. 常用命令

```bash
.venv/bin/python -m pytest -q                                      # 全量(约 5 秒)
.venv/bin/python -m pytest packages/docanon-core/tests/test_job.py -q   # 单个文件
.venv/bin/python -m pytest tests/test_architecture.py -q           # 包边界
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml    # CLI 端到端
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml                 # Web 端到端
```

> **必须用 `.venv/bin/python -m pytest`**：PATH 上的 `pytest` 可能跑在别的 Python 上（缺 `rapidocr`），
> 那样扫描件测试会被静默 skip —— OCR 回归等于没测。

仓库**没有** lint / typecheck / CI / pre-commit，也不打算加（理由见
[docs/architecture.md](docs/architecture.md) §七）。所以"跑通测试 + 贴出输出"就是这里的质量门禁。

## 3. 代码在哪

```
packages/
├── docanon-contract/          引擎与 app 唯一共享层（只准标准库）
├── docanon-engine-ocr/        OCR 引擎
├── docanon-engine-ner-onnx/   ONNX 中文 NER 引擎
├── docanon-engine-ner-llm/    本地大模型 NER 引擎
└── docanon-core/              app：extractors/ → detectors/ → redaction/ + pipeline/job/cli/server
apps/web/                      零构建前端（index.html + app.css + app.js）
apps/desktop/                  Electrobun 壳（开发日常用不到）
tests/                         跨包测试（包边界、可搬运性、文档一致性、e2e/webkit）
```

依赖方向**只有一条**：`core → 引擎 → contract`。引擎包之间互不依赖，各自可整块搬走
（`tests/test_engine_portability.py` 会真的把它们拷到别处 import 一遍）。

## 4. 改代码时的硬规矩

这些不是风格偏好，是被测试锁住的契约（详见 [AGENTS.md](AGENTS.md)）：

| 规矩 | 为什么 | 谁盯着 |
|---|---|---|
| 引擎起不来 → 报错退出，**不许**静默返回空 | 一次"没答上"被当成"零命中"就是漏脱敏 | `prepare_detectors` 预检 + `test_engines.py` |
| 契约层只准标准库；引擎只依赖契约+自己；core 只用引擎公开面 | 否则"整块搬走"失效 | `tests/test_architecture.py` |
| 布局路径只改 `resources.LAYOUT` | 布局知识分散就会漂 | `packages/docanon-core/tests/test_layout.py` |
| 产物命名与账本写入纪律不许改 | 同名覆盖 / 崩溃丢记录 | `test_output_layout.py`、`test_job.py` |
| 命中页 PDF 整页栅格化（不许"盖黑块保留文字层"） | 盖黑块 = 原文仍可复制 = 没脱敏 | `test_pdf_output.py` |
| 改了行为要同步文档 | 文档写旧路径比没文档更坑 | `tests/test_docs.py` |

最后一条特别提醒：`tests/test_docs.py` 会检查文档里点名的路径是否存在、链接能否落地、
提到的测试文件是否存在，**以及 `AGENTS.md` 里那句"N 项"是否等于实际收集数**。
所以加/删测试后，顺手改一下 AGENTS.md 那句话，否则测试会红（这是故意的）。

## 5. 浏览器端检查（改了预览/界面才需要）

壳用的是系统 WebView（macOS = WKWebView），用 Playwright 的 WebKit 内核覆盖同一件事：

```bash
.venv/bin/docanon web -p 8803 -c configs/onnx.yaml &
cd tests/e2e/webkit && npm install && npx playwright install webkit
DOCANON_URL=http://127.0.0.1:8803 node webkit-check.mjs                       # 功能(默认 sample.docx)
DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node webkit-check.mjs # 换格式
```

输出里 `errors` 必须是 `[]`。它不进 pytest（那个目录里有 node_modules），需要手动跑。

## 6. 提交与 PR

- **分支**：`main` 保护；从 `main` 开分支，名字用 `feat/…`、`fix/…`、`refactor/…`、`docs/…`。
- **提交信息**：中文，第一行动词开头说清"做了什么"，正文说"为什么"。一次提交只做一件事。
  例：`后端: 断点续跑 —— 账本每文件落盘 + run --resume`。
- **PR**：按模板填，重点是**贴出 `pytest -q` 的结果行**（没有 CI，人只能看这个）。
  改了文档就说明同步了哪些；改了边界就说明被哪个测试锁住。

## 7. 不要做的事（本项目明确的非目标）

- 不接云端 API、不依赖 Ollama；除本机 `llama-server` 外不联网。
- 不引入 lint/typecheck/CI/pre-commit（单人本地工具，测试即门禁）。
- 不做多用户/权限系统；`mapping.json` 就是本地文件。
- 不做"完美版式还原"；PDF 命中页变位图是安全选择，不是待办。
- 别把 `mapping.json`、模型权重、`var/` 之类的东西提交进来（`.gitignore` 已经挡住，别强行 `-f`）。

## 8. 报告问题

- **漏脱敏 / 敏感内容可能被还原** → 走私密渠道，见 [SECURITY.md](SECURITY.md)。
- 崩溃、格式不支持、界面问题 → 用 [issue 模板](.github/ISSUE_TEMPLATE/bug_report.yml)，
  记得附 `docanon engines` 的输出与版本号；**不要**附真实敏感原文。
