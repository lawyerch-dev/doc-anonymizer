# 基准与模型选型

> 这是"为什么默认用这个模型/这条路线"的证据记录。怎么用工具看 [README](../README.md)，
> 操作边界看 [AGENTS.md](../AGENTS.md)。数字都是实测(Apple M5 / 32GB)，复现脚本在 `scripts/`。

## 两条路线的定位

| 路线 | 依赖 | 定位 |
|---|---|---|
| **ONNX**(编码器式中文 NER) | onnxruntime，无 server | 快、轻、标签集固定；推荐路线（`-c configs/onnx.yaml`） |
| **LLM**(生成式，llama.cpp) | llama-server + 3G 模型 | 灵活（能听指令、能生成自然假名），但慢 30 倍 |

两者可以同时开（配置里都置 `true`），检测结果取并集再去重（`resolve.py`）。

## ONNX 路线（不依赖 llama.cpp）

用**编码器式中文 NER 模型**替代生成式 LLM 做"理解"：

```bash
# 模型在 var/models/onnx/ (默认方案用 gyr66 通用中文 NER; pii-engineer 可选)
docanon run ./samples -o var/out -c configs/onnx.yaml
```

| 后端 | 召回 | 均耗时 | 依赖 |
|---|---|---|---|
| **ONNX 联合**(gyr66 + pii-engineer) + 规则 | **100%** | **34ms** | onnxruntime, 无 server |
| ONNX gyr66(CLUENER) + 规则 | **100%** | **7ms** | 同上 |
| ONNX pii-engineer + 规则 | 83.3% | 9ms | 同上（漏机构名与地址） |
| LLM Qwen3.8-4B | 100% | 1190ms | llama.cpp + 3G 模型 |

- **默认方案(`configs/onnx.yaml`)只要 `gyr66` 一个**：实测它单独就是满召回(12/12, 7ms)，
  比两个模型取并集还快；`pii-engineer` 单独跑会漏机构与地址(10/12)，取并集对它没有增量。
  所以首次"准备"从 780MB 降到 390MB，`pii-engineer` 改成可选（`npm run models --all` 才取）。
- 两个模型取并集时的分工：`gyr66` 出机构/人名/地址，`pii-engineer` 出人名/手机/身份证
- 金额由规则补（两个 NER 都无 AMOUNT 标签）
- 代价：标签集固定，不如 LLM 灵活（不能听指令、不能生成自然假名）

标签 → 本项目实体类型的映射表在 `packages/docanon-core/src/docanon_core/config.py` 的
`DEFAULT_ONNX_ENTITY_MAP`（app 侧词汇表，引擎只收它当参数）。

## LLM 路线：模型对比

```bash
./scripts/download_model.sh Q4_K_M          # 从 ModelScope 下载到 var/models/
./scripts/serve_llm.sh                      # 起 llama-server :8080
.venv/bin/python scripts/bench_models.py    # 自动扫描 var/models/*.gguf 逐个跑基准
```

输出每个模型的**召回率 / 平均耗时 / 内存**；测试样例见 `scripts/bench_models.py` 的 `CASES`。

### 已测基准（Apple M5 / 32GB，6 个中文样例，12 个待识别片段）

| 模型 | 大小 | 召回 | 均耗时 | 内存 |
|---|---|---|---|---|
| **Qwen3.8-4B-Distill Q4_K_M** ✅默认 | 2.8G | 100% | 1.46s | 3.1G |
| Qwen3.5-4B Q4_K_M | 2.7G | 100% | 1.90s | 3.0G |
| Qwen3.5-9B Q4_K_M | 5.7G | 100% | 2.70s | 5.7G |
| MiniCPM5-2B Q4_K_M | 1.6G | 91.7% | 0.56s | 1.8G |
| Anonymizer-1.7B Q4_K_M | 1.1G | 91.7% | 0.62s | 1.6G |

> 6 例样本量小，差距（100% vs 91.7%）仅 1 个未召回，仅供参考；扩大 `CASES` 可提高置信度。
> 专用脱敏模型 Anonymizer（英文训练）在中文上**未超过通用小模型**，印证了"中文脱敏仍靠中文 LLM"。
> 9B 无召回优势却更重，弃用；选型过程见[设计方案](specs/2026-10-05-doc-anonymizer-design.md) §3.2。

## 检测器基准

```bash
.venv/bin/python scripts/bench_detectors.py   # 各检测器(ONNX / LLM)在样例上的表现
```

依赖 `var/models/onnx/*`；要跑 LLM 那一路先起 `serve_llm.sh`。
