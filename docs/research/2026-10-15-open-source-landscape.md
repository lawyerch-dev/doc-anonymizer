# 开源对标调研：离线「OCR → 识别 → 可逆脱敏」产品（2026-10-15）

> 目的：回答「有没有可以直接对标、甚至直接采用的开源项目」。方法：GitHub API 元数据（协议 / 星标 / 最后提交）
> 逐条核对 + 各仓库 README 与 LICENSE 原文通读。
> 商业竞品（LawRedact、零信脱敏、律隐盾）与移动端拆解见 [2026-10-14-competitive-analysis.md](2026-10-14-competitive-analysis.md)，本文不重复那些结论。
> 数据截止 **2026-10-15**。

## 一、结论

**没有对标项目。** 三条证据：

1. **星标断层**：同类仓库能搜到的一大批，几乎全部落在 ≤10⭐ 区间，且多数已停更（§4.2）。
2. **上规模的两个都不做这件事**：Stirling-PDF（94,209⭐）是 PDF 工具箱，Presidio（11.3k⭐）是 PII 识别 SDK——
   都不是「法律场景 + 可逆还原」的产品。
3. **「可逆还原」在开源侧几乎不存在**：同类仓库里只有零星 ≤6⭐ 项目提到 reversible mapping，没有任何一个被验证可用。

→ 不存在「拿一个 MIT 开源项目改造成 LawRedact」这条路。可行路线只有**组件拼装 + 自研工作流**；
而工作流那三层（脱敏渲染产品化、可逆映射、复核工作台）恰恰没有开源参照。

## 二、六条硬条件的交集为空

| 硬条件 | 满足者 |
|---|---|
| MIT 许可 | Stirling-PDF、Presidio、docling，以及一批 ≤10⭐ 项目 |
| 桌面端 + 移动端双端 | SDK 层有（`flutter_edge_ai`，见 §3.5）；**产品层无** |
| 纯本地离线 | Presidio（库）、docling、RapidOCR、OCRmyPDF 等 |
| OCR + PII 识别一体化 | **无**（必须至少两个组件拼：Presidio 无 OCR，RapidOCR 无 PII） |
| 可逆还原 | **无** |
| 星标不低 + 维护活跃 | Stirling-PDF、Presidio、GLiNER、OCRmyPDF 满足——但它们都不满足上面几行 |

## 三、上规模的相关开源（已核实）

### 3.1 Stirling-PDF —— 唯一「能脱敏的成熟 PDF 工具」

- 94,209⭐ · **MIT（带目录级例外）** · 提交于 2026-10-15
- LICENSE 原文：主体 MIT，但 `app/proprietary/`、`app/saas/`、`engine/`、`frontend/editor/src/proprietary/`
  这几处**若存在**则各按其自身 LICENSE——采用前必须读完再决定。
- 能力（README）：50+ PDF 工具，含 redact、OCR、convert、sign。
- 差距：**没有 PII 识别模型**，自动脱敏靠正则/预设；无假名可逆；无移动端；无中文本土实体（案号、发文字号等）。

### 3.2 Presidio —— 识别 + 脱敏的最佳开源底座

- **11.3k⭐ · MIT**；仓库已迁至 data-privacy-stack/presidio（本机克隆核实：LICENSE 为 MIT，HEAD 提交 2026-10-04）
- 组件：analyzer（NER / 正则 / 规则 / 校验和识别器）、anonymizer、image-redactor（含 DICOM）、structured、cli。
- 差距：**是 SDK 不是产品**；无 OCR、无复核 UI、无可逆映射管理、无移动端。
- 官方 README 自带免责声明：不保证找出全部敏感信息。

### 3.3 识别层可直接复用的模型

| 项目 | 协议 | ⭐ | 最近提交 | 说明 |
|---|---|---|---|---|
| GLiNER | Apache-2.0 | 4,096 | 2026-10-05 | 零样本 NER，任意实体类型，PII 场景主流底座 |
| openai/privacy-filter | Apache-2.0 | 2,742 | 2026-04-22 | PII token 分类模型（OpenAI 开源权重） |

两者均为 **Apache-2.0，不是 MIT**；作为依赖引入不影响本项目自身的 MIT。

### 3.4 OCR / 版面层

| 项目 | 协议 | ⭐ | 最近提交 | 备注 |
|---|---|---|---|---|
| OCRmyPDF | **MPL-2.0** | 35,026 | 2026-10-12 | 给扫描 PDF 加可搜索文本层；注意 MPL 非 MIT |
| docling | MIT | 68,894 | 2026-10-14 | 本地文档解析 + OCR；无移动端 |
| RapidOCR | Apache-2.0 | 8,137 | 2026-10-14 | 本项目已用；桌面与移动绑定齐全 |
| PaddleOCR | Apache-2.0 | 91,115 | 2026-09-16 | 生态最大，偏重 |
| MinerU | Apache-2.0 **+ 附加条款** | 81,756 | 2026-10-14 | LICENSE.md 明确含额外商业条款，非纯净 Apache |

### 3.5 端侧 / 跨端推理 SDK（往手机端下沉时的地基）

| 项目 | 协议 | ⭐ | 最近提交 | 端覆盖 | 判定 |
|---|---|---|---|---|---|
| flutter_edge_ai | **MIT** | 640 | 2026-10-14 | Android · iOS · Web · macOS · Windows · Linux | ✅ 唯一 MIT 六端可选 |
| quaynor | **GPL-3.0** | 35 | 2026-08-29 | 桌面 · Android · iOS（Rust 核心 + 6 语言绑定） | ❌ 协议与星标都不符，仅作技术参照 |

**flutter_edge_ai**（[DenisovAV/flutter_edge_ai](https://github.com/DenisovAV/flutter_edge_ai)，前身 `flutter_gemma`）值得单独记一笔：
它是本轮唯一同时满足「MIT + 桌面 + 移动 + 纯本地」的成熟项目 —— 但**它是给开发者的库，不是脱敏产品**，因此不改变§1 的结论。

- **引擎可插拔**：litertlm 引擎（.litertlm，CPU/GPU/NPU）、mediapipe 引擎（官方已标注维护模式）、onnx 引擎（ONNX Runtime GenAI；Web 走 Transformers.js），
  以及 builtin_ai 引擎 —— **直接用操作系统自带的模型，零下载**（Android Gemini Nano、iOS/macOS Apple Foundation Models、Windows AI Foundry、浏览器 Prompt API）。
- **能力**：文本、视觉、音频、函数调用、embeddings、RAG（含 sqlite-vec / Qdrant 向量库）、语音（STT/TTS + VoiceSession）、agent（SKILL.md 技能 + MCP 工具）、诊断。
- **对本项目的意义**：它把「模型能在六端跑起来」这层解决了，但 **PII 检测、脱敏渲染、可逆映射一样都没有**；
  若采用，它替代的是「端侧推理」这一层，不是产品层。是否值得为此引入 Flutter 技术栈，见 competitive-analysis 的移动端拆解。

## 四、落选清单（为什么「星标少 / 停更 / 协议不符」）

### 4.1 名气大但不满足条件

| 项目 | 协议 | ⭐ | 最近提交 | 落选理由 |
|---|---|---|---|---|
| JoshData/pdf-redactor | CC0-1.0 | 213 | **2024-06-13** | 老牌 PDF 文本层涂黑工具，已停更 2 年+；无 PII 模型、无假名、无移动端 |
| docbleach/DocBleach | MIT | 160 | **2023-09-18** | 是 CDR（去宏 / 去隐藏数据），不是 PII 脱敏；停更 3 年 |
| BCHSI/philter-ucsf | BSD-3-Clause | 161 | **2024-08-20** | 临床 PHI 去标识，非法律场景；停更 |
| BishopFox/unredacter | **GPL-3.0** | 8,398 | 2024-03-15 | 方向相反：**还原**被像素化的文字（攻击视角）。顺带反证一条工程结论——像素化不算脱敏 |

### 4.2 同类里最接近的几个——全部 ≤9⭐（按本文标准直接排除，但值得知道它们存在）

| 项目 | 协议 | ⭐ | 最近提交 | 与目标的接近点 |
|---|---|---|---|---|
| MAYA-DATA-PRIVACY/AI-Safe-Plugin | MIT | 35 | 2026-10-03 | AI 聊天实时 PII 脱敏（不是文档产品） |
| PraneelBhatia/redactable | Apache-2.0 | 9 | 2026-06-05 | 确定性优先 + 司法辖区策略包 |
| lawchat-oss/taiwan-legal-deid | MIT | 6 | 2026-10-08 | **法律文书** + 假名 + **可逆映射**（CPU 跑） |
| noirdoc-ai/mask-engine | MIT | 6 | 2026-09-30 | 文档 PII 脱敏 + 假名化 + 可逆 |
| info-wordcab/wordcab-pii | Apache-2.0 | 6 | 2025-09-18 | 基于 GLiNER 的 PII/PHI/PCI 模型集 |
| straightbackward/maskbase | MIT | 4 | 2026-07-09 | macOS 本地 PII 脱敏 + 人工复核（形态最像桌面端） |
| apiotrowski-afk/anon-legal-pl | Apache-2.0 | 3 | 2026-06-24 | 波兰法律文书 PII（Presidio + spaCy） |
| williape/desktop-redactor | MIT | 3 | 2025-08-07 | Presidio 桌面壳 |
| redacted-actual/Android-Redacter | 未声明 | 2 | 2026-01-25 | **Android 端侧 OCR 自动打黑**（移动端唯一像样的尝试） |

表中之外，同类仓库全部落在 0–1⭐ 区间，不再罗列。

## 五、可拼装的四层（唯一可行路线）

| 层 | 候选 | 协议 | 开源是否有现成产品 |
|---|---|---|---|
| OCR / 版面 | RapidOCR、docling、OCRmyPDF、PaddleOCR | 见 §3.4 | 有 |
| 实体识别 | Presidio、GLiNER、openai/privacy-filter | MIT / Apache | 有 |
| 脱敏渲染（保版式回写） | 自研：docx 按 run 改写 / PDF 命中页栅格化 / 图片画框 | — | 组件有，产品无 |
| **可逆映射** | **无**；LawRedact 的加密 .maskmap 属自研 | — | **无** |
| **复核工作台** | **无** | — | **无** |
| **移动端** | SDK 层有 `flutter_edge_ai`（六端，见 §3.5）；成品无（最近的是 2⭐ 的 Android-Redacter） | MIT | **产品层无** |

关键判断：**开源只覆盖前两层**；后三层（脱敏渲染的产品化、可逆映射、复核工作台）没有任何可抄的实现，
而这三层正是商业竞品的收费点。

## 六、对本项目的结论

1. **差异化仍然成立**：商业竞品全部闭源，MIT 开源 + 全离线在信创 / 政务采购里仍是稀缺位（与 competitive-analysis 的定位判断一致）。
2. **可低成本补强的一层**：识别层接 GLiNER / Presidio 的 recognizer，用来扩实体类型，省自研模型的成本。
3. **必须自研且无开源参照的两层**：加密可逆映射、复核工作台 —— 排期按「无外部参照」估，不要按「有开源可改造」估。
4. **移动端有了第一块可用地基，但只到"能跑模型"为止**：`flutter_edge_ai`（§3.5）把六端推理解决了，PII 检测与脱敏仍得自研。
   是否值得为它引入 Flutter 技术栈，见 competitive-analysis 的移动端拆解一节。

## Sources

- Stirling-PDF：https://github.com/Stirling-Tools/Stirling-PDF （LICENSE 原文，2026-10-15）
- Presidio：https://github.com/data-privacy-stack/presidio （11.3k⭐ / MIT，2026-10-15；LICENSE 与 HEAD 提交经本机克隆核实）
- GLiNER：https://github.com/urchade/GLiNER
- Flutter Edge AI：https://github.com/DenisovAV/flutter_edge_ai （MIT / 640⭐ / 六端；元数据经仓库页面核实，2026-10-15）
- quaynor：https://github.com/iBz-04/quaynor （GPL-3.0 / 35⭐）
- OpenAI Privacy Filter：https://github.com/openai/privacy-filter
- OCRmyPDF：https://github.com/ocrmypdf/OCRmyPDF
- docling：https://github.com/docling-project/docling
- RapidOCR：https://github.com/RapidAI/RapidOCR
- PaddleOCR：https://github.com/PaddlePaddle/PaddleOCR
- MinerU：https://github.com/opendatalab/MinerU （LICENSE.md 附加条款原文）
- JoshData/pdf-redactor：https://github.com/JoshData/pdf-redactor （LICENSE = CC0-1.0）
- DocBleach：https://github.com/docbleach/DocBleach
- philter-ucsf：https://github.com/BCHSI/philter-ucsf
- unredacter：https://github.com/BishopFox/unredacter
- §4.2 各项目：各自 GitHub 仓库页与 LICENSE / README
- 元数据口径：GitHub REST API 的 /repos 与 /search/repositories；星标与最后提交均为 **2026-10-15** 快照。
