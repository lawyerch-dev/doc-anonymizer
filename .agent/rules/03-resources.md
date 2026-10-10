# 资源根、配置与模型

**布局只有一处真相**：`packages/docanon-core/src/docanon_core/resources.py` 的 `LAYOUT`（键→相对路径）。
要挪 `configs/`、`apps/web/dist/`、`samples/`、`var/models` 这些目录，只改这张表；
`packages/docanon-core/tests/test_layout.py` 会立刻报出哪里对不上。访问器一律走 `path(key)`。

**资源根是找出来的**（逐级向上找含 `configs/default.yaml` 的目录），不是 `parents[N]` 猜的：
找不到就抛 `ResourceRootError`，让你设 `DOCANON_ROOT`。

**可写状态与资源分家**（`resources.WRITABLE` = `models` / `user_configs`）：这几个键按
`DOCANON_DATA` 解析，其余按资源根。打包成 `.app` 后资源根在包内、可能还是只读的随机挂载点
（App Translocation），模型写那儿等于白下。源码树里不设这个变量，两个根重合、行为跟以前一样。
配置里的 `onnx.model_dirs` 走 `resolve_model_dir()`（按数据根），**不要**改回 `resolve()` ——
那会把模型指进 `.app` 里去。

- 可选资源按需下载、不进包：`var/libreoffice`（旧格式转换用，`scripts/fetch_libreoffice.sh` 取；
  `convert.find_soffice` 顺序 = `DOCANON_SOFFICE` > 系统安装 > 这里）。

- `-c` 的配置文件按**资源根**解析；`onnx.model_dirs` 按**数据根**（见上）；命令行上的输入/输出路径按**调用者 cwd**。
- 配置读不到就报错（不许静默退化成空配置——那看起来和"没启用"一样，`packages/docanon-core/tests/test_resources.py` 锁两条）。
- 不带 `-c` 走 `configs/default.yaml`：`onnx_ner`/`llm_ner` 均 `false`，只剩规则+词典，
  同一个 `samples/example.txt` 实测少掉 `PERSON` 与 `LOCATION`。桌面壳固定 `configs/onnx.yaml`。
- `configs/llm.yaml` 的 `llm.model_id` 选了目录里的模型 → **Web** 开跑前自动起 `llama-server`
  （`server/llm_server.py`，本机 127.0.0.1、端口 8090 起，`DOCANON_LLM_PORT` 可改）；留空 = 自备服务，那时才要自己 `./scripts/serve_llm.sh`（CLI 一律自备）。
- `configs/llm_models.yaml` 是**可下载的大模型目录**（不是脱敏方案，故不在 L1 下拉里 ——
  `profiles.NOT_A_PROFILE` 白名单管着）。界面的「本地大模型」靠它列选项与下载；
  收录纪律见 `docs/specs/2026-10-09-llm-model-download-design.md`（只收核实过的地址）。
- `configs/onnx_models.yaml` 是**识别模型目录**（同上，也不在 L1 下拉里），供首次"初始化"用：
  `server/prepare.py` 按当前方案补齐缺的模型（`POST/GET /api/prepare`、`/api/prepare/cancel`）。
  两条纪律：**下载前先对候选端点各取 256KB 测速、挑最快的**（国内直连官方 HF 常不可达）；
  **文件全齐才算装好**（少一个就报错，不让"少一层"的结果蒙混过去）。**模型不进安装包**（5.9G），
  首次使用按需下载 —— 界面对用户只说"正在准备"，不提模型/镜像/文件数。

**部署契约**（写在根 `pyproject.toml`）：只支持 editable 安装与打包根两种形态，
**不做 wheel 自包含**——前端 vendor 232MB、模型 GB 级，本来就不该进包。

**模型**：`configs/onnx.yaml` 默认只要 `var/models/onnx/gyr66`（约 390MB；`pii-engineer` 可选）：

```bash
npm run models                   # 默认走 hf-mirror(官方 HF 本机实测超时), HF_ENDPOINT 可换
./scripts/download_onnx_models.sh --check   # 只探端点通不通
```

LLM 路线：`./scripts/download_model.sh` 取 GGUF 到 `var/models/`（Web 里选中模型即下载），再起服务 ——
CLI 用 `./scripts/serve_llm.sh`，Web 自动起。
