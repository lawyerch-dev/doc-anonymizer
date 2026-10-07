<h1 align="center">doc-anonymizer</h1>

<p align="center"><b>本地文档脱敏</b> · 中文优先 · 全离线 · 保留原格式</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Platform: macOS arm64" src="https://img.shields.io/badge/platform-macOS%20arm64-lightgrey.svg">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg">
  <img alt="No network" src="https://img.shields.io/badge/network-offline%20by%20design-success.svg">
</p>

<p align="center">
  <img src="docs/images/web-ui.png" width="900" alt="Web 界面：左侧选文档，中间预览原文，点「开始脱敏」后右侧预览保留原格式的脱敏件">
</p>

人名、手机号、身份证、银行卡、邮箱、IP、统一社会信用代码、密钥、自定义敏感词 —— 识别并抹掉，
输出**同格式**文件 + 可还原对照表。**不联网、不上传、不依赖云端 API。**

## 特性

- **中文优先**：规则 + 中文词典 + 中文 NER（ONNX）三路并用。
- **全离线**：无云端调用；可选的 LLM 路线也只连本机 `llama-server`。
- **保留原格式**：docx 按 run 改写、xlsx/csv 改单元格、pdf/图片涂黑，前后可左右对照。
- **召回优先**：拿不准的一律标出，命中位置与来源可查。
- **可还原**：`mapping.json` 记「原文 ↔ 替换值」，`restore` 还原文本产物。
- **不许静默少一层**：引擎起不来就在跑前报错退出，不产出"少了识别"的结果。
- **可续跑**：账本每处理完一个文件就落盘，`--resume` 不重做已完成部分。
- **三种用法**：CLI / 浏览器 / 桌面窗口，同一套引擎与配置。

## 快速上手

前置：Apple Silicon macOS + Python 3.11/3.12。

```bash
git clone https://github.com/lawyerch/doc-anonymizer && cd doc-anonymizer
./scripts/dev.sh setup      # 装依赖(幂等) + 环境自检
./scripts/dev.sh web        # → http://127.0.0.1:8000
./scripts/dev.sh desktop    # 桌面壳(需 Hutch)
```

`dev.sh` 是开发入口：`setup` `web` `desktop` `test` `cli` `engines` `models` `website` `doctor`（`./scripts/dev.sh help` 看全部）。
缺 ONNX 模型（`configs/onnx.yaml` 的中文 NER）时取一次：`./scripts/dev.sh models` —— 约 830MB，
默认走 `hf-mirror.com`（官方 huggingface.co 在部分网络不可达），`HF_ENDPOINT` 可换端点。
它只是包装，底层就是 `docanon` / `pytest` / `hutch` —— 下文用的是原始命令，出问题可直接排查。
逐步走一遍：[docs/quickstart.md](docs/quickstart.md)。

## 用法

### 命令行

```bash
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml        # 处理文件或目录
.venv/bin/docanon run ./案件 -o var/out -c configs/onnx.yaml --resume  # 断了接着跑
.venv/bin/docanon engines -c configs/onnx.yaml                         # 这份配置跑了几层检测
.venv/bin/docanon restore var/out/sample.md.redacted.md --mapping var/out/mapping.json
```

退出码：`0` 全部处理 · `1` 输入/配置/引擎有问题（一个文件都不写）· `2` 有文件没产出结果
（格式不支持 / 抽取失败 / 被中断）—— `2` 是提示，不是跑坏了。

### Web 界面

```bash
./scripts/fetch_file_viewer.sh                       # 首次: 预览资源(232MB, gitignore)
.venv/bin/docanon web -p 8000 -c configs/onnx.yaml
```

选示例或上传 → 预览原文 → 脱敏 → 对照预览 + 命中统计；「运行日志」给逐条溯源
（哪个引擎、在哪个位置、命中什么、替换成什么）。仅监听 `127.0.0.1`、无鉴权（本机自用）。

接口：`/` `/app.css` `/app.js` `/health` `/api/presets` `/api/upload` `/api/anonymize`
（后两个入参 `{filename, content_b64}` / `{preset|token}`，出参含 `counts` 与 `trace`；上传上限 50MB）。

### 官网与文档站（可选）

```bash
./scripts/dev.sh website                      # → http://127.0.0.1:4321（首次自动 npm install）
npm run build -w @doc-anonymizer/website      # 静态输出到 apps/website/dist/，任意静态服务器都能发
```

Astro 5 + Starlight（搜索/TOC/上下页内置），内容直接来自本仓库的 markdown
（清单 `apps/website/content-manifest.json`）；组件在共享包 [`apps/ui`](apps/ui/README.md)
（`@doc-anonymizer/ui`，来自 [velora-ui](https://github.com/ColorlibHQ/velora-ui)，MIT），
**产品前端以后换栈时引同一个包**，外观与组件不会分叉。
细节、框架选型的实测对比与坑见 [apps/website/README.md](apps/website/README.md)。

### 桌面壳（可选）

```bash
cd apps/desktop && hutch install && npm start   # 系统 WebView, :8770
```

见 [apps/desktop/README.md](apps/desktop/README.md)。

## 支持与产物

| 输入 | 产物 | 脱敏方式 |
|---|---|---|
| `.docx` | `x.docx.redacted.docx` | 按 run 改写文字，保留格式与表格 |
| `.xlsx` / `.csv` | `x.xlsx.redacted.xlsx` | 改写单元格，保留表结构 |
| `.pdf`（文字层） | `x.pdf.redacted.pdf` | 命中页涂黑（**该页变位图**） |
| `.pdf`（扫描件）/ `.png` `.jpg` `.tiff` … | 同上 / `x.png.redacted.png` | OCR 定位后按字符宽度比例涂黑 |
| `.txt` / `.md` | `x.txt.redacted.txt` | 按行替换纯文本 |

命名 `<源文件全名>.redacted.<原扩展名>`，保留相对子目录。`-o` 目录里两个账本（按源文件**累加**，可分批跑）：

- `manifest.json` —— 每文件 `ok` / `error` / `unsupported`。**只有 `ok` 是脱敏过的。**
- `mapping.json` —— 原文 ↔ 替换值。**切勿与脱敏件一起外发或提交。**

## 配置

`configs/`：`default.yaml`（规则 + 词典）· `onnx.yaml`（+ 中文 NER，日常推荐）·
`llm.yaml`（+ 本地大模型，先 `./scripts/serve_llm.sh`）。

- 策略按实体类型配：`pseudonym`（同类同实体固定假名）/ `placeholder`（`<PHONE_1>`）/
  `mask`（`138****0000`）/ `remove`（直接删）；自定义词写在 `dictionary`，记为 `CUSTOM`。
- 配置里的相对路径（如 `onnx.model_dirs`）按**资源根**解析（从 `configs/default.yaml` 逐级向上找，
  可用 `DOCANON_ROOT` 指定），与 cwd 无关；命令行上的输入/输出路径按 cwd。

## 检测引擎

| 引擎 | 做什么 | 依赖 |
|---|---|---|
| `rule` | 身份证/手机/银行卡/邮箱/IP/统一社会信用代码/密钥/金额 | 无 |
| `dictionary` | 自定义业务敏感词 → `CUSTOM` | 无 |
| `onnx_ner` | 中文 NER（人名/机构/地址等），34ms/例、无需 server | `var/models/onnx/*` |
| `llm_ner` | 本地大模型 NER，可听指令、生成自然假名 | `llama-server` + GGUF |

`docanon engines` 会报每层是否可用（含原因）与实际能力；选型与基准见 [docs/benchmarks.md](docs/benchmarks.md)。

## 已知限制

- **PDF 命中页整页变位图**（文字层消失、不可选中/搜索/再编辑）。这是安全保证：给文字层盖黑块的话
  原文照样能复制出来。未命中的页原样保留。
- docx 的**页眉、页脚、脚注、文本框不抽取**（正文段落与表格单元格已覆盖）。
- `restore` 只支持文本产物（txt/md/csv）；`remove` 删掉的原文没有锚点，无法还原。
- 打码后同形的值（两个号码都 mask 成一样）会还原成错的原文。
- `.doc` / `.xls` / `.wps` 不支持（记 `unsupported`，退出码 2）；GBK 的 CSV 需先转 UTF-8。
- 输出目录不能放在输入目录里面，否则下一次 run 会把上次的 `.redacted.*` 当新文档再脱敏一遍。
- **辅助人工复核，不保证零漏检**：OCR 错字、罕见写法都可能漏。交付前请人工过一遍，尤其扫描件与表格。

## 文档

| 我想… | 看 |
|---|---|
| 逐步跑通、常见问题 | [docs/quickstart.md](docs/quickstart.md) |
| 参与开发（环境、测试、提交、PR） | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 改代码前必读的契约与坑 | [AGENTS.md](AGENTS.md) |
| 五包结构、硬边界、决策记录、搬迁历史 | [docs/architecture.md](docs/architecture.md) |
| 模型选型与基准数字 | [docs/benchmarks.md](docs/benchmarks.md) |
| 脚本清单 | [scripts/README.md](scripts/README.md) |
| 版本变更 | [CHANGELOG.md](CHANGELOG.md) |
| 漏脱敏等安全问题怎么报 | [SECURITY.md](SECURITY.md) |
| 最初的设计方案（历史） | [docs/specs/2026-10-05-doc-anonymizer-design.md](docs/specs/2026-10-05-doc-anonymizer-design.md) |

[MIT](LICENSE) © 2026 [lawyerch](https://github.com/lawyerch) ·
致谢 [RapidOCR](https://github.com/RapidAI/RapidOCR)、[pypdfium2](https://github.com/pypdfium2-team/pypdfium2)、
[python-docx](https://github.com/python-openxml/python-docx)、[openpyxl](https://foss.heptapod.net/openpyxl/openpyxl)、
[llama.cpp](https://github.com/ggml-org/llama.cpp)、[file-viewer](https://github.com/flyfish-dev/file-viewer)、
[Electrobun](https://github.com/blackboardsh/electrobun)、[velora-ui](https://github.com/ColorlibHQ/velora-ui)
