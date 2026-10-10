# scripts/ 一览

**日常只用一个**：仓库根的 npm scripts（`npm run setup` / `dev` / `dev:website` / `test` / `doctor` …）。
`scripts/dev.sh` 是它们的**实现层**（也能直接用：`./scripts/dev.sh help`），它包装下面这些脚本与命令，`setup` 会调用 `setup_dev.sh` 与（缺预览资源时）
`fetch_file_viewer.sh`；`web`/`webui`/`desktop`/`website` 分别起 `docanon web`、产品界面开发态（后端 + Vite dev）、
壳里的 `npm start`、`website/` 的 `astro dev`；`dist` 打可分发版（侧车 + 资源根收进 `.app`，详见
[apps/desktop/README.md](../apps/desktop/README.md)）。

| 脚本 | 干什么 | 依赖 | 用法 |
|---|---|---|---|
| `dev.sh` | **实现层**（npm scripts 调它）：装环境、起 Web/官网/桌面壳、跑测试、取模型、打可分发版、自检 | 无（包装其余） | `./scripts/dev.sh help` |
| `setup_dev.sh` | 建 `.venv`、装五个包 editable + 测试依赖、字节码缓存重定向到 `var/pycache`（幂等） | python3.12 / pip | `./scripts/setup_dev.sh` |
| `make_samples.py` | 生成 `samples/`（txt/md/docx/pdf 文字/扫描/png/xlsx/csv） | python-docx / openpyxl / pypdfium2 / Pillow | `.venv/bin/python scripts/make_samples.py` |
| `download_model.sh` | 从 ModelScope 下载 GGUF 到 `var/models/` | curl | `./scripts/download_model.sh [Q4_K_M]` |
| `serve_llm.sh` | 起 llama-server（OpenAI 兼容 :8080） | brew 的 `llama.cpp` | `./scripts/serve_llm.sh [端口] [模型路径]` |
| `fetch_file_viewer.sh` | 拉 file-viewer 预构建包到 `var/vendor/file-viewer` | npm | `./scripts/fetch_file_viewer.sh` |
| `fetch_libreoffice.sh` | 取 LibreOffice 到 `var/libreoffice`（旧版 .doc/.xls/.wps 自动转换用） | curl / hdiutil(macOS) | `./scripts/fetch_libreoffice.sh [版本]` |
| `download_onnx_models.sh` | 取两个 ONNX NER 模型到 `var/models/onnx/`（约 830MB；默认走 hf-mirror 镜像） | curl | `./scripts/download_onnx_models.sh [--check] [--only gyr66]` |
| `make_app_icon.sh` | 由 `apps/desktop/icon.svg` 生成 `icon.iconset/`（macOS）与 `icon.png`（Windows，**必须 256px**），**打包输入，提交进仓库** | rsvg-convert | `./scripts/make_app_icon.sh [--check]` |
| `bench_models.py` | 逐个 GGUF 跑召回/耗时/内存基准 | 先起 `serve_llm.sh` | `.venv/bin/python scripts/bench_models.py` |
| `bench_detectors.py` | 各检测器（ONNX / LLM）在样例上的表现 | `var/models/onnx/*` | `.venv/bin/python scripts/bench_detectors.py` |

一律在**仓库根**执行。相对路径两种定位方式：`download_model.sh` / `serve_llm.sh` 按调用者 **cwd**
（写的是 `var/models/…`）；`make_samples.py` / `bench_*.py` / `fetch_file_viewer.sh` 按**脚本自身位置**。
`docanon` 又不同：它的相对路径按**资源根**（见 `resources.LAYOUT`）。

- `samples/` 不要手改：改 `make_samples.py` 重跑（生成的 PDF 必须内嵌中文 TTF 子集，
  否则 file-viewer 中文预览乱码，详见 [AGENTS.md](../AGENTS.md)）。
- `download_model.sh` / `fetch_file_viewer.sh` / `download_onnx_models.sh` 拉到 `var/`（gitignore），
  换机器要重跑。官方 `huggingface.co` 在部分网络下不可达，所以模型默认从 `hf-mirror.com` 取；
  换端点用 `HF_ENDPOINT=…`，先探通不通用 `--check`（脚本支持 `--only` 单个模型、`--dest` 换目录）。
- `fetch_libreoffice.sh` 也拉到 `var/libreoffice`（gitignore），默认走**国内镜像**（腾讯云，
  `DOCANON_LIBREOFFICE_MIRROR` 可换成官方或别的镜像）；macOS 解 `.dmg`，Linux 用 `dpkg-deb` 解官方 `.deb`。
- WebKit 兼容检查在 [tests/e2e/webkit/](../tests/e2e/webkit/)（node + Playwright），不在 `scripts/`。
- 基准结果与选型结论：[docs/benchmarks.md](../docs/benchmarks.md)。
