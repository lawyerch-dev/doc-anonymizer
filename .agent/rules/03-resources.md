# 资源根、配置与模型

**布局只有一处真相**：`packages/docanon-core/src/docanon_core/resources.py` 的 `LAYOUT`（键→相对路径）。
要挪 `configs/`、`apps/web/dist/`、`samples/`、`var/models` 这些目录，只改这张表；
`packages/docanon-core/tests/test_layout.py` 会立刻报出哪里对不上。访问器一律走 `path(key)`。

**资源根是找出来的**（逐级向上找含 `configs/default.yaml` 的目录），不是 `parents[N]` 猜的：
找不到就抛 `ResourceRootError`，让你设 `DOCANON_ROOT`。

- 可选资源按需下载、不进包：`var/libreoffice`（旧格式转换用，`scripts/fetch_libreoffice.sh` 取；
  `convert.find_soffice` 顺序 = `DOCANON_SOFFICE` > 系统安装 > 这里）。

- `-c` 的配置文件、`configs/*.yaml` 里的相对路径（如 `onnx.model_dirs`）按**资源根**解析；
  命令行上的输入/输出路径按**调用者 cwd**。
- 配置读不到就报错（不许静默退化成空配置——那看起来和"没启用"一样，`packages/docanon-core/tests/test_resources.py` 锁两条）。
- 不带 `-c` 走 `configs/default.yaml`：`onnx_ner`/`llm_ner` 均 `false`，只剩规则+词典，
  同一个 `samples/example.txt` 实测少掉 `PERSON` 与 `LOCATION`。桌面壳固定 `configs/onnx.yaml`。
- `configs/llm.yaml` 需先 `./scripts/serve_llm.sh` 把 llama-server 起到 :8080。
- `configs/llm_models.yaml` 是**可下载的大模型目录**（不是脱敏方案，故不在 L1 下拉里 ——
  `profiles.NOT_A_PROFILE` 白名单管着）。界面的「本地大模型」靠它列选项与下载；
  收录纪律见 `docs/specs/2026-10-09-llm-model-download-design.md`（只收核实过的地址）。

**部署契约**（写在根 `pyproject.toml`）：只支持 editable 安装与打包根两种形态，
**不做 wheel 自包含**——前端 vendor 232MB、模型 GB 级，本来就不该进包。

**模型**：`configs/onnx.yaml` 需要 `var/models/onnx/{gyr66,pii-engineer}`（约 830MB）：

```bash
npm run models                   # 默认走 hf-mirror(官方 HF 本机实测超时), HF_ENDPOINT 可换
./scripts/download_onnx_models.sh --check   # 只探端点通不通
```

LLM 路线：`./scripts/download_model.sh` 取 GGUF 到 `var/models/`，再 `./scripts/serve_llm.sh`。
