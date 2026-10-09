# Agent Note: 本地大模型在界面里选并下载

Status: implemented
Date: 2026-10-09

## 问题

产品界面的 LLM 路线要用户填两项不认识的东西：**模型服务地址**（`http://127.0.0.1:8080/v1`）与
**模型名**（`qwen3.8-4b`）。而模型文件本身得在终端跑 `./scripts/download_model.sh Q4_K_M` 去下
（1–3GB，还得自己等、自己知道下到哪）。于是"想用大模型"这件事整个落在终端里，界面只剩下两个
看不懂的输入框 —— 用户既不知道填什么，也不知道去哪拿模型。

## 决策

1. **目录是数据**：`configs/llm_models.yaml` 存"有哪些模型可下"（名字、一句话、仓库、文件名、大小）。
   加模型改文件，不改代码。
2. **界面里下载**：后台任务 + 进度 + 取消 + `Range` 续传 + `.part` 原子改名。
3. **接口只收目录里的 `id`，不收 URL**：下载地址一律由目录的 `repo`+`file` 拼出。
4. **只收核实过的地址**：收录前逐个 HTTP 核实（仓库页 + 文件列表页），并遵守"不把没实测过的数字
   安到别的模型头上" —— 所以首批只收 benchmarks 里实测过的两个 4B。
5. **选中模型不改 `llm.model`**：那个字段是 llama-server 的 `--alias`（`serve_llm.sh` 固定
   `qwen3.8-4b`），不是 gguf 文件名；把别名写成文件名会让"用别名启动的服务"对不上。界面改成讲清
   "该用哪个文件、怎么起服务"，地址与模型名降级到折叠的"自定义服务（高级）"。

## 代价与取舍

- **产品边界变了**：这是本项目第一次让应用主动联网。README 徽章从 `offline by design` 改成
  `offline by default`，并在正文、SECURITY.md、官网文案都写明唯一例外。**已明确接受。**
- **只收 2 个模型**看着少，但每一个的地址与大小都是核过的 —— 目录里放没核过的地址，等于做了个
  点了必坏的按钮。以后加模型按同一纪律补。
- **下载是进程内任务**：关掉服务进程，`.part` 留着，下次点下载接着续；不做断点以外的持久化
  （本机单人用，不值得）。
- **仍要手动起 llama-server**：模型下好只解决了"拿到文件"，`llama.cpp` 的安装与服务启动仍是终端一步
  （界面给出可复制的命令）。要做成"一键跑起来"是另一件事。
  > 后续（2026-10-09 晚）：这条非目标已被推翻 —— 界面改回"选一个模型就直接用"，服务由
  > `server/llm_server.py` 在开跑前自动起好（见 CHANGELOG 的 Unreleased）。

## 证据

- 设计：`docs/specs/2026-10-09-llm-model-download-design.md`
- 实现：`packages/docanon-core/src/docanon_core/server/downloads.py`、`configs/llm_models.yaml`
- 守卫：`packages/docanon-core/tests/test_model_download.py`（结构、URL 拼接、拒绝面、
  以及"`download_model.sh` 与目录说的是同一个仓库与文件名"）
- 顺带修的坑：`configs/` 下新增 yaml 会被 `list_profiles` 的 `glob("*.yaml")` 当成"脱敏方案"
  显示进 L1 下拉 → 加 `profiles.NOT_A_PROFILE` 白名单 + 测试。
