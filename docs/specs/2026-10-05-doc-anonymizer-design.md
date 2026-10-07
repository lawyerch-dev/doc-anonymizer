# 文档脱敏工具 (doc-anonymizer) — 设计方案

- 日期: 2026-10-05
- 状态: 已落地（2026-10-07 复核；定稿后的改动见 §10）
- 路线: 方案 B —— 混合管道 + 可插拔抽取器

## 1. 目标与范围

团队内部使用、在 Apple Silicon Mac 本地运行的中文文档脱敏工具。

- 输入: DOCX / TXT / MD / 电子版 PDF / 扫描件 PDF / 图片 / XLSX / CSV
- 敏感项: 规则类 PII(身份证/手机号/银行卡/邮箱/IP/统一社会信用代码)、
  实体类(人名/公司/机构/地名)、自定义业务敏感词、密钥/凭证/金额
- 原则: 召回优先(宁多勿漏)
- 输出: 按实体类型分别配置策略(假名/占位符/打码/删除/可还原)
- 形态: CLI 为主 + 轻量 Web(二期)

## 2. 总体架构

```
文件 ──► [抽取器 Extractor] ──► 结构化文本块 Block(含定位)
     ──► [检测器 Detector]   ──► Detection(span, type, source)
     ──► [合并去重 Resolve]  ──► 无重叠 span 集合
     ──► [策略 Strategy]     ──► 替换文本(经全局映射表保证一致)
     ──► [回写 Rewriter]     ──► 脱敏后文件 + 映射表(mapping.json)
```

三个可插拔点，全部通过注册表按文件类型/配置选择:

1. **抽取器**: 每种文件类型一个实现，产出带定位信息的 `Block`。
   - 文字层: `text_file` (DOCX/TXT/MD)、`pdf` (pypdfium2 文字层)、`table` (XLSX/CSV)
   - 无文字层: `ocr_image` (RapidOCR, 输出文字 + bbox)
2. **检测器**: `rule`(正则)、`dictionary`(自定义词表)、`llm_ner`(本地大模型)
3. **策略**: `pseudonym` / `placeholder` / `mask` / `remove`

## 3. 技术选型

| 环节 | 选型 | 理由 |
|---|---|---|
| OCR | **RapidOCR 2.x (ONNXRuntime)** | 基于 PP-OCRv6 转 ONNX，中文强、带 bbox、轻量、跨平台 |
| 大模型推理 | **llama.cpp (`llama-server`)** | GGUF 量化省内存、Metal 加速、可嵌入软件、OpenAI 兼容；Ollama 底层也是它 |
| 中文模型 | **Qwen3.5-9B-Instruct (GGUF Q4_K_M)** | 2026-10 实测选型，见 3.2 |
| LLM 接入 | llama-server 的 OpenAI 兼容接口 | 语言无关，随时可换进程内绑定 |
| 模型下载源 | **ModelScope** `unsloth/Qwen3.5-9B-GGUF` | 国内直连 ~16MB/s；HF/hf-mirror 当前仅 ~1MB/s 或不通 |

### 3.2 模型选型(2026-10 调研 + 实测)

调研 Hugging Face / ModelScope 实际可用仓库(非猜测):

- 最新一代为 **Qwen3.8**(官方开源 27B), 27B 在 32GB Mac 上偏重, 不符合"轻便/省内存"。
- **Qwen3.5** 提供 0.8B / 2B / **4B** / 9B / 27B, 官方开源、中文强。
- 专用 PII 编码器(piiranha / GLiNER2 / nvidia-GLiNER)经核实**语言标签均无中文**(仅英/法/德/西等),
  对中文文档不适用; 故中文脱敏仍以"中文 LLM + 规则/词典"为主。

**实测对比**(Apple M5 / 32GB, 6 例中文样例, 12 个待识别片段):

| 模型 | 大小 | 召回 | 均耗时 | 内存 |
|---|---|---|---|---|
| **Qwen3.8-4B-Distill Q4_K_M** ✅ | 2.8G | 100% | 1.46s | 3.1G |
| Qwen3.5-4B Q4_K_M | 2.7G | 100% | 1.90s | 3.0G |
| Qwen3.5-9B Q4_K_M | 5.7G | 100% | 2.70s | 5.7G |
| MiniCPM5-2B Q4_K_M | 1.6G | 91.7% | 0.56s | 1.8G |
| Anonymizer-1.7B Q4_K_M | 1.1G | 91.7% | 0.62s | 1.6G |

**结论**: 默认选 **Qwen3.8-4B-Distill Q4_K_M**(最新一代蒸馏, 100% 召回, 内存/耗时约为 9B 的一半)。
9B 无召回优势却更重, 弃用。基准脚本 `scripts/bench_models.py` 可复现。

### 3.3 运行环境实测

- 机器: Apple **M5 / 32GB**, macOS 26.6
- Python: 3.12.13(venv);注意 3.14 无 onnxruntime 轮子
- llama.cpp: brew `llama.cpp` 0.5.0(build 11146)
- RapidOCR: 2.x + onnxruntime 1.30, PP-OCRv6 模型

### 3.1 运行时选型结论(laya-mlx / vLLM / MLX / llama.cpp)

| 运行时不 | 定位 | 适合本项目? |
|---|---|---|
| **llama.cpp** | 通用 LLM/VLM C++ 推理引擎, GGUF | ✅ **首选**：省内存、可嵌入、跨平台、OpenAI 兼容 |
| MLX | Apple 官方数组框架, `mlx-lm` | ⭕ 备选：Mac 上最快，但偏 Python、集成/可移植性弱 |
| vLLM | 服务器级高吞吐推理引擎 | ❌ 面向 NVIDIA/AMD 数据中心，不支持 Metal |
| laya-mlx | 类型化判定(分类/打分/护栏)专用 | ⏸ 暂不加，可作为"检测判断器/护栏"二期接入 |

### 3.4 ONNX 检测后端(可选, 不依赖 llama.cpp)

用 ONNXRuntime 跑**编码器式中文 NER**替代生成式 LLM 做"理解", 更轻更快、无需 server。

- 候选(现成 `model.onnx`, 免 torch 导出):
  - `protectai/gyr66-bert-base-chinese-finetuned-ner-onnx` — 通用中文 NER(CLUENER 系)
  - `pii-engineer/PII-Engineer-Chinese-NER-v1.0` — 中文 PII(人名/手机/身份证/地址)
- 两模型**取并集** + 规则(补金额): 实测 **召回 100%, 34ms, 无 server**
- 对比: LLM Qwen3.8-4B 100% 但 1190ms、需 3G 模型 + llama.cpp
- 代价: 标签集固定, 不如 LLM 灵活(不能听指令/生成自然假名)
- 配置: `configs/onnx.yaml`; `docanon run ... -c configs/onnx.yaml`

### 3.5 原位回写 + 友好 Web

- **原位回写**(`writers.py`): 脱敏结果写回**原格式**, 供前后对比
  - docx: python-docx 按 run 回写(保留格式) + 表格单元格
  - xlsx/csv: 回写单元格
  - pdf: 文字层按 `get_charbox` 涂黑; 扫描页按 OCR bbox 涂黑; 合并为 PDF
  - 图片: 涂黑 bbox
- **友好 Web**(零构建): 基于 [file-viewer](https://github.com/flyfish-dev/file-viewer) 预构建包
  - 流程: 选示例/上传 → 预览原文 → 脱敏 → **同查看器预览原件与脱敏件**
  - 资源: `scripts/fetch_file_viewer.sh` 拉取到 `var/vendor/file-viewer`(gitignore)
  - 后端: `GET /api/presets`、`POST /api/upload`、`POST /api/anonymize`、`/file-viewer/*`

## 4. 数据模型

- `Block`: `block_id`, `text`, `locator(page/bbox/paragraph/cell)`, `kind`
- `Span`: `start`, `end`, `text`
- `Detection`: `span`, `entity_type`, `source`, `confidence`
- `MappingStore`: 全局 `entity_type + 原文 → 替换值`，保证全文一致并可还原

## 5. 脱敏策略

| 策略 | 说明 | 例 |
|---|---|---|
| `pseudonym` | 同类同实体固定假名，跨全文一致 | 张三 → 林芳 |
| `placeholder` | 占位符 + 序号 | `<PHONE_1>` |
| `mask` | 部分打码保留格式 | 138****0000 |
| `remove` | 整段删除 | 密钥直接抹去 |

按类型在 `configs/default.yaml` 的 `strategies` 中配置，缺省走 `DEFAULT`。

## 6. 非目标(YAGNI)

- 不做云端调用，不依赖 Ollama
- 一期不做手写体专精、不做表格版式完美还原
- 不做多用户/权限系统(可还原映射表先用本地文件)

## 7. 里程碑

1. M1: 文字层(A 线) 抽取 + 正则/词典检测 + 全部策略 + CLI ✅
2. M2: OCR(B 线) 图片/扫描件，bbox 涂黑回写 ✅
3. M3: LLM NER 检测器接入 llama.cpp ✅
4. M4: 轻量 Web ✅

## 8. 验证记录 (2026-10-05)

- 单元测试: `7 passed`
- A 线: txt/md/docx/pdf(文字)/xlsx/csv 全部通过
- B 线: png/扫描 PDF 经 RapidOCR 识别 → 命中行涂黑(实测新增 16.7 万暗像素)
- LLM NER: llama-server + Qwen3.5-9B 正确识别 人名/公司/金额/地点
  - 假名一致性: 张三→崔禾、李四→苏舟, 全文一致
- Web: `/health`、首页、`/api/anonymize`(文本与图片)均通过

## 9. 风险

- Python 3.14 尚无 onnxruntime 轮子 → 用 3.11/3.12 虚拟环境
- 扫描件 OCR 错误会传导到脱敏 → 召回优先 + 可评测
- 大模型判断有幻觉 → 规则保底 + 后置护栏

## 10. 后续变更（2026-10-07）

本节只记"设计定稿之后改掉/补上的东西"。**现状以 `README.md`、`AGENTS.md` 与
[`docs/architecture.md`](../architecture.md) 为准**，本节只是索引。

- **引擎可移植边界**：新增 `src/docanon/contract.py`（只依赖标准库）作为引擎与 app 之间唯一的共享层，
  由 `tests/test_architecture.py` 用 AST 锁死；实体词表留在 app 侧（`config.py` 的 `DEFAULT_ONNX_ENTITY_MAP`）
  当引擎的必填构造参数；引擎按配置指纹在进程内缓存；`docanon engines` 与跑前 `prepare_detectors`
  保证"少一层检测必须报错，不许静默"。
- **资源根**：相对路径不再依赖 cwd，统一走 `resources.py`；资源根靠标记文件（`configs/default.yaml`）
  逐级向上找，找不到直接报错（`DOCANON_ROOT` 可覆盖）—— 旧的 `parents[2]` 猜法在非 editable 安装下
  会读到空配置，而空配置看起来就像"一层引擎都没启用"。
- **账本与续跑**：`job.py` 的 `manifest.json`/`mapping.json` 每处理完一个文件就原子落盘；
  `run --resume` 以"标 `ok` **且产物文件仍在**"为跳过条件；退出码 0/1/2 见 README。
- **原位回写**（设计 §3.5 落地）：docx 按 run 改写、xlsx/csv 改写单元格、pdf 与图片涂黑。
  代价是 **pdf/图片产物是位图**（文字层消失），这条补进了 README「已知限制」。
- **桌面壳**：定为 **Electrobun**（系统 WebView）。Tauri 因 WKWebView 下 PDF 抖动被弃（commit `67330ba`），
  Electron 因体积被弃。壳侧三条实测约束（项目根按标记文件找、壳被强杀时 sidecar 自己了断、
  只认自己拉起的后端）见 `apps/desktop/README.md`。
- **还原（`restore`）**：只支持文本产物；`remove` 策略的原文不可还原（替换值为空串，不是锚点）。
- **布局**：下载/构建得到的资产统一收进 `var/`（`var/models`、`var/vendor`），产物目录仍由 `-o` 决定；
  壳的 `apps/desktop/build/` 是唯一例外（Hutch 的 `buildFolder` 只接受项目相对路径）。
  所有布局路径集中在 `resources.LAYOUT` 一张表里，`tests/test_layout.py` 锁住。
- **测试**：从设计期的 7 项长到 71 项；`samples/` 由 `scripts/make_samples.py` 生成（PDF 必须内嵌中文 TTF 子集）。

