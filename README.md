<h1 align="center">doc-anonymizer</h1>

<p align="center"><b>本地文档脱敏工具</b> · 中文优先 · 全离线 · 保留原格式</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Platform: macOS arm64" src="https://img.shields.io/badge/platform-macOS%20arm64-lightgrey.svg">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg">
  <img alt="No network" src="https://img.shields.io/badge/network-offline%20by%20design-success.svg">
</p>

<p align="center">
  <img src="docs/images/web-ui.png" width="900" alt="Web 界面：左侧选文档，中间预览原文，点「开始脱敏」后右侧预览保留原格式的脱敏件">
</p>

把一份中文文档丢进去，**人名、手机号、身份证、银行卡、邮箱、IP、统一社会信用代码、密钥、自定义敏感词**
会被识别并抹掉，输出**与原文相同格式**的文件，外加一份可还原的对照表。
全过程在本机完成：**不联网、不上传、不依赖云端 API**。

```bash
git clone https://github.com/lawyerch/doc-anonymizer && cd doc-anonymizer
./scripts/setup_dev.sh                                             # 建环境 + 装依赖
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml    # 跑一遍内置样例
```

第一次用建议看 **[5 分钟快速上手](docs/quickstart.md)**（含界面截图与常见问题）。

## 特性

- **中文优先**：规则 + 中文词典 + 中文 NER 模型（ONNX）三路并用，专治中文文档里的姓名/机构/地址。
- **全离线**：没有任何云端调用。可选的"本地大模型"路线也只连本机的 `llama-server`。
- **保留原格式**：docx 按 run 改写、xlsx/csv 改写单元格、pdf/图片涂黑 —— 前后可以左右对照着看。
- **召回优先（宁多勿漏）**：拿不准的一律标出来；命中位置与来源都在运行日志里可查。
- **可还原**：`mapping.json` 记住"原文 ↔ 替换值"，`docanon restore` 能把文本产物还原回去。
- **不许静默少一层**：任何引擎起不来，跑之前就报错退出（退出码 1），不会给你一份"少了实体识别"的脱敏件。
- **大卷宗能续跑**：账本每处理完一个文件就落盘，Ctrl+C 或崩溃之后 `--resume` 接着跑，不重做已完成的部分。
- **三种用法**：命令行、浏览器界面、桌面窗口（Electrobun 壳），同一套引擎与同一份配置。

## 快速上手

```bash
# 1) 环境（Apple Silicon macOS；Python 3.11/3.12 建议）
./scripts/setup_dev.sh

# 2) 处理单个文件或整个目录
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml

# 3) 打开界面（浏览器访问 http://127.0.0.1:8000）
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml
```

> 不带 `-c` 时走 `configs/default.yaml`，其中 ONNX/LLM 检测器默认关闭（只剩规则 + 词典）。
> 要人名/机构/地名，请带上 `-c configs/onnx.yaml`。

## 用法

### 命令行

```bash
# 处理目录（保留相对子目录结构）
.venv/bin/docanon run ./案件 -o var/out -c configs/onnx.yaml

# 跑到一半中断/有文件失败 —— 接着跑，已完成的不重做
.venv/bin/docanon run ./案件 -o var/out -c configs/onnx.yaml --resume

# 这份配置到底跑了几层检测？别猜，列出来（每个引擎: 可用/不可用带原因 + 实际能力）
.venv/bin/docanon engines -c configs/onnx.yaml

# 还原（只支持文本产物: txt/md/csv）
.venv/bin/docanon restore var/out/sample.md.redacted.md --mapping var/out/mapping.json
```

退出码：`0` 全部处理 · `1` 输入/配置/引擎有问题（一个文件都不写）· `2` 有文件没产出结果
（格式不支持、抽取失败、被中断）—— `2` 是提示，不是"跑坏了"。

### Web 界面

```bash
./scripts/fetch_file_viewer.sh                  # 首次: 拉预览资源(约 232MB, 已 gitignore)
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml
```

左侧选内置示例或上传文件 → 中间预览原文 → 点「开始脱敏」→ 右侧预览脱敏件，并给出命中统计与下载。
「运行日志」弹窗里是逐条命中溯源（哪个引擎在哪个位置命中了什么）。

仅监听 `127.0.0.1`、无鉴权（本机自用），接口很小：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/`、`/app.css`、`/app.js` | 前端页面（零构建静态件） |
| GET | `/health` | `{ok, pid}` |
| GET | `/api/presets` | 内置示例清单 |
| GET | `/samples/*`、`/file-viewer/*`、`/uploads/*`、`/outputs/*` | 静态资源 |
| POST | `/api/upload` | `{filename, content_b64}` → `{token, filename, url}`（上限 50MB） |
| POST | `/api/anonymize` | `{preset}` 或 `{token}` → `{output_name, output_url, counts, kind, trace}` |

### 桌面壳（可选）

把同一套界面装进原生窗口（系统 WebView，不内置 Chromium）。开发与测试都不需要它。

```bash
cd apps/desktop && hutch install && npm start    # 端口 8770
```

细节（含三条实测约束）见 [apps/desktop/README.md](apps/desktop/README.md)。

## 支持的文件与产物

产物命名 `<源文件全名>.redacted.<原扩展名>`，并保留源文件的相对子目录（同名不同类型的文件不会互相覆盖）。

| 输入 | 产物 | 脱敏方式 |
|---|---|---|
| `.docx` | `x.docx.redacted.docx` | 按 run 改写文字，保留格式与表格 |
| `.xlsx` / `.csv` | `x.xlsx.redacted.xlsx` | 改写单元格，保留表结构 |
| `.pdf`（文字层） | `x.pdf.redacted.pdf` | 命中页涂黑（**该页变位图**，见「已知限制」） |
| `.pdf`（扫描件）/ `.png` `.jpg` `.tiff` … | 同上 / `x.png.redacted.png` | OCR 定位后按字符宽度比例涂黑 |
| `.txt` / `.md` | `x.txt.redacted.txt` | 按行替换纯文本 |

每个 `-o` 目录里还会更新两个账本（按源文件**累加**，可分批往同一个目录跑）：

- `manifest.json` —— 每个源文件一条记录：`ok`（含产物路径与命中数）/ `error`（含原因）/ `unsupported`。
  **只有标 `ok` 的才是脱敏过的。**
- `mapping.json` —— 原文 ↔ 替换值对照表（含全部敏感原文）。**切勿与脱敏件一起外发或提交。**

## 配置

见 [`configs/`](configs)：`default.yaml`（规则+词典）、`onnx.yaml`（+ONNX 中文 NER，Web 与桌面壳默认）、
`llm.yaml`（+本地大模型，需先 `./scripts/serve_llm.sh` 把 `llama-server` 起到 :8080）。

- 每种实体类型用哪种策略，在 `strategies` 里配：`pseudonym`（同类同实体固定假名）/ `placeholder`
  （`<PHONE_1>`）/ `mask`（`138****0000`）/ `remove`（直接删）。
- 自定义敏感词写在 `dictionary` 里，命中记为 `CUSTOM`。
- 配置文件里的相对路径（如 `onnx.model_dirs`）按**资源根**解析，与你当前在哪个目录敲命令无关；
  命令行上的输入/输出路径仍按当前目录。资源根靠 `configs/default.yaml` 逐级向上找，找不到会直接报错
  （可用 `DOCANON_ROOT` 指定）。

## 检测引擎

引擎在 `packages/` 里各自成包，跑前会逐个 `ready()` 自检；想确认"这份配置到底跑了几层"，用
`docanon engines`。

| 引擎 | 做什么 | 依赖 |
|---|---|---|
| `rule` | 正则：身份证/手机/银行卡/邮箱/IP/统一社会信用代码/密钥/金额 | 无 |
| `dictionary` | 自定义业务敏感词 → `CUSTOM` | 无 |
| `onnx_ner` | 中文 NER（人名/机构/地址等），34ms/例、无需 server | `var/models/onnx/*` |
| `llm_ner` | 本地大模型 NER，能听指令、生成自然假名 | `llama-server` + GGUF |

模型怎么选的、基准数字怎么来的：[docs/benchmarks.md](docs/benchmarks.md)。

## 已知限制

- **命中敏感信息的 PDF 页会整页变位图**（该页文字层消失，不可选中/搜索/再编辑）。这是**安全保证**：
  给文字层盖黑块的话原文照样能复制出来。没命中的页保持原样。
- **docx 的页眉、页脚、脚注、文本框不抽取**（正文段落与表格单元格已覆盖）。
- **`restore` 只支持文本产物**（txt/md/csv）；docx/xlsx/pdf/图片是回写产物，没有可替换的纯文本。
  `remove` 策略删掉的原文没有锚点，也无法还原（会提示有几条还原不了）。
- 打码后相同的值（两个号码都 mask 成同形）会还原成错的原文。
- `.doc` / `.xls` / `.wps` 不支持（清单里记 `unsupported` 并返回退出码 2）；GBK 的 CSV 需先转 UTF-8。
- 输出目录不能放在输入目录里面，否则下一次 run 会把上次的 `.redacted.*` 当新文档再脱敏一遍。
- **它是辅助人工复核的工具，不是"绝对安全"的保证**：OCR 错字、罕见写法都可能漏检。
  交付前请人工过一遍，尤其是扫描件与表格。

## 架构一览

```
packages/
├── docanon-contract/          引擎与 app 之间唯一的共享层（只依赖标准库）
├── docanon-engine-ocr/        OCR 引擎（RapidOCR）
├── docanon-engine-ner-onnx/   ONNX 中文 NER 引擎
├── docanon-engine-ner-llm/    本地大模型 NER 引擎
└── docanon-core/              app：抽取 → 检测 → 替换回写 + 账本 + CLI + Web

依赖方向永远是 core → 引擎 → 契约，由测试机械检查；三个引擎包各自独立、可整块搬走。
```

为什么这么分、目录为什么这么摆：[docs/architecture.md](docs/architecture.md)。

## 文档

| 我想… | 看 |
|---|---|
| 5 分钟跑通、常见问题 | [docs/quickstart.md](docs/quickstart.md) |
| 参与开发（环境、测试、边界、提交规范） | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 改代码前必须知道的契约与坑 | [AGENTS.md](AGENTS.md) |
| 五包结构、决策记录、搬迁历史 | [docs/architecture.md](docs/architecture.md) |
| 模型选型与基准数字 | [docs/benchmarks.md](docs/benchmarks.md) |
| 脚本都有哪些 | [scripts/README.md](scripts/README.md) |
| 版本变更 | [CHANGELOG.md](CHANGELOG.md) |
| 漏脱敏等安全问题怎么报 | [SECURITY.md](SECURITY.md) |
| 最初的设计方案（历史记录） | [docs/specs/2026-10-05-doc-anonymizer-design.md](docs/specs/2026-10-05-doc-anonymizer-design.md) |

## 环境要求

- **Apple Silicon macOS**（OCR/模型选型都按这个平台实测）。
- **Python 3.10–3.13**（建议 3.11/3.12；3.14 目前 `onnxruntime`/`rapidocr` 可能没有轮子）。
- 可选：`llama.cpp`（LLM 路线）、`npm`（拉预览资源）、Hutch+Bun（桌面壳）。

## 贡献与许可

欢迎 issue 与 PR —— 先读 [CONTRIBUTING.md](CONTRIBUTING.md)（含"没有 CI，所以请贴测试输出"这类约定）。
安全问题请走 [SECURITY.md](SECURITY.md) 的私密渠道。

[MIT](LICENSE) © 2026 [lawyerch](https://github.com/lawyerch)

致谢：[RapidOCR](https://github.com/RapidAI/RapidOCR)、[pypdfium2](https://github.com/pypdfium2-team/pypdfium2)、
[python-docx](https://github.com/python-openxml/python-docx)、[openpyxl](https://foss.heptapod.net/openpyxl/openpyxl)、
[llama.cpp](https://github.com/ggml-org/llama.cpp)、[file-viewer](https://github.com/flyfish-dev/file-viewer)、
[Electrobun](https://github.com/blackboardsh/electrobun)。
