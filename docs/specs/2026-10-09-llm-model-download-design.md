# 本地大模型：目录选择 + 界面内下载 设计

> 状态：已批准，待实施
> 日期：2026-10-09
> 现状以 [README](../../README.md)、[AGENTS.md](../../AGENTS.md)、[architecture](../architecture.md) 为准；本文是当时的完整设计。

## 背景与问题

产品界面里用 LLM 路线要填两项：**模型服务地址**（`http://127.0.0.1:8080/v1`）与**模型名**（`qwen3.8-4b`）。
对非技术用户这两项都不可理解：

- 不知道该填什么，也不知道去哪拿模型；
- 模型文件本身要靠 `./scripts/download_model.sh Q4_K_M` 在终端里下（1–3GB，还得自己等），
  界面上没有任何提示它存在、大小多少、下完放哪；
- 于是"想用 LLM 路线"这件事整体落在终端里，界面只剩下两个看不懂的输入框。

## 目标与非目标

**目标**

- L3 里把"地址 + 模型名"换成**模型下拉**：看得懂的名字 + 一句话 + 大小 + 是否已下载。
- **在界面里点下载**，带进度与取消；下完自动落到 `var/models/`，并给出该填的地址与模型名。

**非目标**

- 不做模型市场：不搜索、不列全部可下载模型、不让用户填任意 URL。
- 不做多任务并发下载（本机单人用，一次一个够）。
- 不管 `llama.cpp` 的安装与 `llama-server` 的启动（仍是终端一步）。

**产品边界的明确改动**

README 徽章 `network: offline by design` 与正文"不联网、不上传"改成
**"除你主动点下载外不联网"**。这是本次唯一的对外承诺变化，已确认接受。

## 数据：目录只有一处真相

新增 `configs/llm_models.yaml`（与其它配置同在资源根，**用户可自己加条目**）：

```yaml
# 可选的大模型（本地跑）。名字与一句话是给用户看的；repo/file 用来拼下载地址。
models:
  - id: qwen3.8-4b-distill
    name: 通用首选（4B 蒸馏）
    hint: 实测 12 处敏感信息全部认出，内存约 3G。装一个就够用。
    repo: empero-ai/Qwen3.8-4B-Distill-GGUF
    file: Qwen3.8-4B-Q4_K_M.gguf
    size_gb: 2.78
    recommended: true
  - id: qwen3.5-4b
    name: 备选（4B）
    hint: 实测同样 12 处全认出，比首选稍慢一点（1.9 秒/例）。
    repo: unsloth/Qwen3.5-4B-GGUF
    file: Qwen3.5-4B-Q4_K_M.gguf
    size_gb: 2.74
```

**两条收录纪律**：

1. **只收实测过的**：`size_gb` 与 hint 里的结论都必须来自 [benchmarks](../benchmarks.md) 的实测表；
   网上抄来的地址不核实（HTTP 200 + 文件列表页确认）不许进目录。
2. **不把没测过的数字安到别的模型头上**：`MiniCPM5-1B` / `Anonymizer-1.7B` / `Qwen3.5-9B`
   暂不收录（前者实测数据对不上、后两者查不到仓库或已被弃用）。

## 后端

新模块 `packages/docanon-core/src/docanon_core/server/downloads.py`（只管"下载一个 gguf"，
不认识 HTTP；旋钮与状态都在这里，`routes.py` 只做胶水）。

- **只收 id，不收 URL**：下载地址由目录条目的 `repo` + `file` 拼出（`https://www.modelscope.cn/models/{repo}/resolve/master/{file}`）。
  接口不接受任意 URL —— 否则就是一个"任意下载/S S R F"洞。另加一道防御：`file` 不含 `/` 与 `..`。
- 流式落盘到 `var/models/<file>.part`，完成后 `os.replace` 成 `var/models/<file>`（原子，不留半截文件）。
- **断点续传**：`.part` 已存在时带 `Range: bytes=<已下字节>-` 续传；服务端不支持 Range 就从头来。
- 一次只允许一个下载任务；重复请求返回 409。
- 进度状态放模块级单例（本机单人用，不需要持久化）：`{id, state, done_bytes, total_bytes, error}`。
  `state ∈ idle|downloading|done|error|cancelled`。
- 取消：置标志位，循环里检查，退出后**保留 `.part`**（下次可续）。

接口（都挂在既有 `/api/models` 命名空间下）：

| 方法 | 路径 | 语义 |
|---|---|---|
| `GET` | `/api/models` | 既有 `onnx_dirs` / `llm` 之外，**新增** `llm_models: [{id,name,hint,size_gb,recommended,file,downloaded}]` |
| `POST` | `/api/models/download` | 入参 `{id}`；起步并返回 202 + 状态；未知 id → 400；已有任务在跑 → 409 |
| `GET` | `/api/models/download` | 当前任务状态（无任务时 `state: idle`） |
| `POST` | `/api/models/download/cancel` | 请求取消 |

**为什么 `size_gb` 要放进接口**：按钮上必须先说清"要占 2.78G"，不能点下去才知道。

## 前端

`ConfigPanel` 的 L3「本地大模型」：

- 未勾「本地大模型」→ 什么都不显示（沿用现有按需显示）。
- 勾了 → **模型下拉**（目录里的条目：名字 + 一句话 + 大小 + 「推荐」标记 + 已下载标记）：
  - 已下载 → 选中即把 `llm.file`/`llm.model` 落成该 gguf 的文件名（`llama-server` 的模型名就是
    文件路径，`served_model_name` 默认取文件名），并显示"已下载，可直接用"；
  - 未下载 → 显示大小与「下载」按钮；下载中显示进度条（已下/总量 + 百分比）与「取消」。
- 折叠的「自定义服务（高级）」保留原来的**地址 + 模型名**两个输入框 —— 自定义端口的 `llama-server`
  或别的 OpenAI 兼容服务仍要能配，不能被下拉挤掉。
- 下载完成后**不自动改地址**：地址与模型名仍由上面那条规则写（避免悄悄改用户的配置）。

## 错误处理（沿用"不许静默少一层"）

- 下载失败（网络断、磁盘满、404）→ 状态置 `error` 并**原样显示原因**，不吞。
- 缺 `llama.cpp` / 服务没起 → 仍是运行期预检的 400 + 原因（本次不改）。
- 磁盘写入失败 → 报错并保留 `.part`。

## 测试与守卫

| 项 | 动作 |
|---|---|
| `configs/llm_models.yaml` 的结构 | 新测试：每条必须齐 `id/name/hint/repo/file/size_gb`，`id` 唯一，`file` 不含 `/` |
| `/api/models` 的 `llm_models` | 扩展 `test_api_models_lists_onnx_dirs_and_llm_defaults`：字段齐、`downloaded` 是布尔 |
| 下载接口的**拒绝面** | 新测试：未知 id → 400；`file` 带路径分隔符的条目 → 不参与拼接（防穿越） |
| 不真下载 2.7G | 测试只覆盖"状态机 + 参数校验 + 拼接出的 URL 正确"，不跑真网络 |
| 文档 | README 徽章与"不联网"表述同步（中英）；`03-resources.md` 补目录文件 |

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 目录里的仓库/文件名写错 → 下载必坏 | 收录前逐个 HTTP 核实（本次已核）；测试只校验结构与拼接，不假装联网对得上 |
| 下载 2–3GB 中途断 | `.part` + Range 续传；失败给原因不吞 |
| 应用联网破坏"离线"预期 | README 徽章与表述明确改成"除你主动点下载外不联网" |
| 任意 URL 下载（SSRF） | 接口只收目录 id；URL 一律由目录拼；`file` 再查一遍无分隔符 |
| 用户在下载中关页面 | 后端任务继续（进程内），重开页面能查到进度；进程退出则 `.part` 留着下次续 |

## 实施步骤概览

1. `configs/llm_models.yaml` + 结构测试（含 `file` 无分隔符）。
2. `server/downloads.py`：状态机、Range 续传、原子落盘、单任务与取消。
3. `routes.py`：三个接口 + `llm_models` 列表；`profiles` 侧提供目录读取与 `downloaded` 判断。
4. 前端：模型下拉 + 进度 + 取消 + 「自定义服务」折叠；`types.ts`/`api.ts` 补类型与调用。
5. 文档：README 中英（徽章 + 表述）、`03-resources.md`、CHANGELOG、决策笔记。
