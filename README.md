# doc-anonymizer

本地文档脱敏工具 —— 在 Apple Silicon Mac 上跑，中文优先。
输入文档 → 抽取文字(+坐标) → 规则/词典/大模型检测敏感信息 → 按类型替换 → 输出脱敏文件 + 映射表。

设计见 [docs/specs/2026-10-05-doc-anonymizer-design.md](docs/specs/2026-10-05-doc-anonymizer-design.md)。

## 技术栈

- **OCR**: RapidOCR 2.x (ONNXRuntime, PP-OCRv6 模型, 中文强、带坐标)
- **大模型**: llama.cpp (`llama-server`, OpenAI 兼容) + **Qwen3.8-4B-Distill** GGUF
  - 实测选型(见下表): 4B 蒸馏版召回 100%, 仅 3.1G 内存、1.46s/例, 胜过 9B
  - 量化 `Q4_K_M`(2.8G); 追求更省可换 Qwen3.5-4B / MiniCPM5-2B
  - 模型来源: ModelScope(国内直连 ~16MB/s)
- **CLI/Web**: Python 标准库 + 极简 Web, 无重依赖

## 安装

> 建议 Python 3.11/3.12。3.14 目前 onnxruntime/rapidocr 可能无轮子。

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[ocr,dev]'
```

## 下载并启动本地大模型

```bash
./scripts/download_model.sh Q4_K_M     # 从 ModelScope 下载 (~6 分钟)
./scripts/serve_llm.sh                 # 启动 llama-server :8080
# 另开一个终端, 打开 config/default.yaml 里 detectors.llm_ner: true
```

## 快速开始

```bash
# 处理单个文件或目录 (默认规则+词典)
docanon run ./samples -o ./out

# 启动轻量 Web
docanon web --port 8000

# 还原
docanon restore ./out/sample.md.redacted.txt --mapping ./out/mapping.json
```

示例文档由 `scripts/make_samples.py` 生成, 覆盖 txt/md/docx/pdf(文字)/pdf(扫描)/png/xlsx/csv。

### 产物与清单

输出目录按源文件的相对路径建子树, 文件名保留源扩展名, 因此同名不同类型的文件不会互相覆盖:

```
docs/告知书/明细.docx   ->   out/告知书/明细.docx.redacted.txt
docs/债权人/明细.txt    ->   out/债权人/明细.txt.redacted.txt
```

每次 run 还会写两个文件:

- `manifest.json` —— 每个源文件一条记录: `ok`(含产物路径与命中数) / `error`(含原因) / `unsupported`(格式不支持)。**只有 manifest 里标 `ok` 的文件才是脱敏过的。**
- `mapping.json` —— 原文↔脱敏值对照表, 含全部敏感信息原件, **切勿与脱敏文件一起外发**。

退出码: `0` 全部处理; `2` 有文件未产出结果(格式不支持或抽取失败); `1` 输入路径不存在。

### 已知限制

- 输出是纯文本(`.redacted.txt`)或图片, 不是可回交的 DOCX/PDF; 表格的行列结构在转换中丢失。
- `.doc` / `.xls` / `.wps` 暂不支持(会明确报出, 不再静默跳过); GBK 编码的 CSV 需要转成 UTF-8 再跑。
- DOCX 里的表格单元格、页眉页脚、脚注当前不抽取 = 不脱敏; 文字页+扫描页混排的 PDF 会整份失败。
- `restore` 在 `remove` 策略命中后不可用, 两个号码打码后相同时会还原成错的原文。
- 输出目录不要放在输入目录里面, 否则下一次 run 会把上一次的 `.redacted.txt` 当成新文档再脱敏一遍。

## 友好 Web 界面(推荐给非技术同事)

```bash
./scripts/fetch_file_viewer.sh                # 首次: 拉取 file-viewer 预览资源(约 232MB, 已 gitignore)
docanon web --port 8000 -c config/onnx.yaml   # 浏览器打开 http://127.0.0.1:8000
```

流程：**左侧选内置示例(或上传) → 中间 file-viewer 预览原文 → 点「开始脱敏」→ 右侧同一查看器预览保留原格式的脱敏件**，并给出命中统计与下载。

- 预览基于 [file-viewer](https://github.com/flyfish-dev/file-viewer)（浏览器端只读预览，Apache-2.0）
- 脱敏**保持原格式**：docx→docx、xlsx→xlsx、pdf→pdf、图片→图片，便于左右对比
- 零构建：直接引用 file-viewer 预构建包，无 node 构建链
- 预览窗格铺满高度；默认**浅色模式**；已隐藏 file-viewer 自带工具栏（搜索/缩放/下载…），避免控件溢出
- 图片/扫描件按**字符宽度比例（CJK=2/ASCII=1）只涂黑敏感片段**，不再整行涂黑

## 多模型对比

```bash
./scripts/download_model.sh Q4_K_M          # 下载更多模型到 models/
.venv/bin/python scripts/bench_models.py    # 自动扫描 models/*.gguf 逐个跑基准
```

输出每个模型的 **召回率 / 平均耗时 / 内存**。测试样例见 `scripts/bench_models.py` 的 `CASES`。

### 已测基准 (Apple M5 / 32GB, 6 个中文样例, 12 个待识别片段)

| 模型 | 大小 | 召回 | 均耗时 | 内存 |
|---|---|---|---|---|
| **Qwen3.8-4B-Distill Q4_K_M** ✅默认 | 2.8G | 100% | 1.46s | 3.1G |
| Qwen3.5-4B Q4_K_M | 2.7G | 100% | 1.90s | 3.0G |
| Qwen3.5-9B Q4_K_M | 5.7G | 100% | 2.70s | 5.7G |
| MiniCPM5-2B Q4_K_M | 1.6G | 91.7% | 0.56s | 1.8G |
| Anonymizer-1.7B Q4_K_M | 1.1G | 91.7% | 0.62s | 1.6G |

> 6 例样本量小, 差距(100% vs 91.7%)仅 1 个未召回, 仅供参考; 扩大 `CASES` 可提高置信度。
> 专用脱敏模型 Anonymizer(英文训练)在中文上**未超过通用小模型**, 印证了"中文脱敏仍靠中文 LLM"。

## ONNX 路线(可选, 完全不依赖 llama.cpp)

用**编码器式中文 NER 模型**（ONNXRuntime 跑）替代生成式 LLM 做"理解"，更轻、更快、无需 server：

```bash
# 模型已下载到 models/onnx/ (gyr66 通用中文NER + pii-engineer 中文PII)
docanon run ./samples -o out_onnx -c config/onnx.yaml
```

| 后端 | 召回 | 均耗时 | 依赖 |
|---|---|---|---|
| **ONNX 联合**(gyr66 + pii-engineer) + 规则 | **100%** | **34ms** | onnxruntime, 无 server |
| LLM Qwen3.8-4B | 100% | 1190ms | llama.cpp + 3G 模型 |

- 两个模型取并集：`gyr66` 出机构/人名，`pii-engineer` 出人名/手机/地址/身份证
- 金额由规则补（两个 NER 都无 AMOUNT 标签）
- 代价：标签集固定，不如 LLM 灵活（不能听指令、不能生成自然假名）

## 配置

见 [config/default.yaml](config/default.yaml)：敏感词表、各类型脱敏策略、LLM 地址。

## 目录结构

```
src/docanon/
├── extractors/   抽取器(按文件类型可插拔, 含 RapidOCR)
├── detectors/    检测器(规则/词典/LLM)
├── strategies.py 脱敏策略
├── resolve.py    重叠合并
├── mapping.py    全局映射表(一致 + 可还原)
├── pipeline.py   编排
├── cli.py        命令行
└── web/          轻量 Web
```

## 非目标

不依赖 Ollama / 云端；一期不做完美版式还原与权限系统。
