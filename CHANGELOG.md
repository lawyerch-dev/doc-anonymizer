# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，
变更记录格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added

- **官网与文档站**：`apps/website/`（**Astro 5 + Starlight** + Tailwind CSS 4）——搜索/TOC/上下页/多语言
  内置，静态输出 `dist/`；内容按 `content-manifest.json` 从仓库 markdown 同步（源仍是那些 .md），
  `./scripts/dev.sh website` 起开发服务器。选型对比（依赖 241M vs Next 537M、构建 0.7s vs 3–4s、
  内置搜索 vs 手写）见 [apps/website/README.md](apps/website/README.md)。
- **共享组件包**：`apps/ui/`（`@doc-anonymizer/ui`，npm workspaces）—— velora 组件与设计 token
  只放一份，网站与将来的产品前端共用（[velora-ui](https://github.com/ColorlibHQ/velora-ui)，MIT）。


## [0.1.0] — 2026-10-07

首个可用版本：CLI + Web + 桌面壳三件套，三条检测路线（规则/词典、ONNX NER、本地大模型 NER），
八种输入格式，产物保留原格式并可还原。

### Added

- **抽取**：txt/md、docx（正文段落 + 表格单元格）、pdf（文字层按 charbox、扫描页走 OCR）、
  图片（png/jpg/tiff/webp）、xlsx/csv。
- **检测**：`rule`（身份证/手机/银行卡/邮箱/IP/统一社会信用代码/密钥/金额）、`dictionary`（自定义敏感词）、
  `onnx_ner`（中文 NER，实测 100% 召回 / 34ms / 无需 server）、`llm_ner`（本地 `llama-server`）。
- **脱敏策略**：`pseudonym`（同类同实体固定假名）/ `placeholder` / `mask` / `remove`，按实体类型配置。
- **产物**：docx 按 run 回写、xlsx/csv 改写单元格、pdf 与图片按坐标涂黑；
  命名 `<源文件全名>.redacted.<原扩展名>` 且保留相对目录。
- **账本**：`manifest.json`（`ok`/`error`/`unsupported` 三态）+ `mapping.json`（原文↔替换值，可还原）；
  每处理完一个文件就原子落盘，`run --resume` 可续跑（要求产物仍在）。
- **CLI**：`run` / `restore` / `engines` / `web`，退出码 `0|1|2` 区分"全部完成/输入有误/有文件没产出"。
- **引擎自检**：`docanon engines` 列出每个引擎的可用性与实际能力（`capabilities()`/`ready()` 自述）。
- **Web 界面**：选内置示例或上传 → file-viewer 预览原文 → 一键脱敏 → 同查看器看脱敏件；
  命中统计与逐条溯源（`/api/anonymize` 返回 `trace`）。
- **桌面壳**：Electrobun（系统 WebView）+ Python sidecar。
- **文档**：快速上手、架构与目录设计、基准与选型、贡献指南、安全策略、更新日志。
- **一条命令起步**：`scripts/dev.sh`（装环境 / 起 Web / 起桌面壳 / 起文档站 / 跑测试 / 取模型 / 环境自检）与
  `scripts/download_onnx_models.sh`（官方 HF 不可达时默认走 `hf-mirror.com`，`HF_ENDPOINT` 可换）。

### Changed

- 代码拆成五个包（`packages/`）：`docanon-contract` + 三个引擎包 + `docanon-core`；
  依赖方向由包与 `pyproject.toml` 机械检查（`tests/test_architecture.py`）。
- 配置改名 `configs/with_llm.yaml` → `configs/llm.yaml`；默认产物目录 `out/` → `var/out`。
- 可再生资产（模型权重、预览资源、产物、字节码缓存）统一收进 `var/`（一条 gitignore 覆盖）。
- 布局路径收敛到 `resources.LAYOUT` 一张表（挪目录只改一处，有测试盯着）。
- 前端从单文件拆成 `index.html` + `app.css` + `app.js`（仍零构建）。
- 安装从 `pip install -e '.[ocr,dev]'` 改为 `./scripts/setup_dev.sh` / `requirements-dev.txt`。

### Fixed

- **`restore` 遇 `remove` 策略会把原文撒满全篇**：空替换值进了反向表，`str.replace("")` 把原文插到
  每个字符之间。现在空串只进正向表，还原统一走 `restorable_items()`，并对无法还原的条目给出提示。
- **Web 请求路径没有 unquote**：中文文件名的上传件在预览/下载处一律 404（接口自己发的 URL 就是中文路径）。
- 桌面壳在 dev 构建下拿系统 `python3` 起后端（`import.meta.dir` 指进 `.app` 内部）；改为按标记文件
  向上找项目根，找不到就报错退出。
- 壳被强杀时后端孤儿化占住端口：新增 `DOCANON_EXIT_WITH_PARENT` 父进程监视，sidecar 自己了断。
- 端口上蹲着旧孤儿时壳会开出一个"假窗口"：`/health` 现在带 pid，壳只认自己拉起的后端。
- `bench_models.py` 扫描已搬走的 `models/`（一个模型都找不到）；bench 脚本往不存在的 `src/` 塞 `sys.path`。
- 非 editable 安装下静默读到空配置（看起来像"一层引擎都没启用"）：资源根改为逐级向上验证，找不到直接报错。

### Security

- **命中敏感信息的 PDF 页整页栅格化**（该页文字层消失）：给文字层盖黑块的话原文仍可被复制/搜索，
  那等于没脱敏。未命中的页原样保留矢量文字与体积。由 `test_pdf_output.py` 锁死。
- 引擎起不来时**不产出任何文件**（退出码 1），不会把"少一层检测"的结果报成已处理。
- `mapping.json` 含全部敏感原文，文档各处明确标注"切勿与脱敏件一起外发"。

[Unreleased]: https://github.com/lawyerch/doc-anonymizer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lawyerch/doc-anonymizer/releases/tag/v0.1.0
