# scripts/ 一览

一律在**仓库根**执行。脚本里的相对路径按资源根解析
（`packages/docanon-core/src/docanon_core/resources.py` 的 `LAYOUT`），
所以从别的目录调用会指错地方。

| 脚本 | 干什么 | 依赖 | 用法 |
|---|---|---|---|
| `make_samples.py` | 生成 `samples/`（覆盖 txt/md/docx/pdf 文字/扫描/png/xlsx/csv） | python-docx / openpyxl / pypdfium2 / Pillow | `.venv/bin/python scripts/make_samples.py` |
| `download_model.sh` | 从 ModelScope 下载 GGUF 到 `var/models/` | curl | `./scripts/download_model.sh [Q4_K_M]` |
| `serve_llm.sh` | 起 llama-server（OpenAI 兼容 :8080） | brew 的 `llama.cpp` | `./scripts/serve_llm.sh [端口] [模型路径]` |
| `fetch_file_viewer.sh` | 拉 file-viewer 预构建包到 `var/vendor/file-viewer` | npm | `./scripts/fetch_file_viewer.sh` |
| `bench_models.py` | 逐个 GGUF 跑召回/耗时/内存基准 | 先起 `serve_llm.sh` | `.venv/bin/python scripts/bench_models.py` |
| `bench_detectors.py` | 各检测器（ONNX / LLM）在样例上的表现 | `var/models/onnx/*` | `.venv/bin/python scripts/bench_detectors.py` |

基准结果与选型结论记在 [docs/benchmarks.md](../docs/benchmarks.md)。

注意：
- `make_samples.py` 生成的 PDF **必须内嵌中文 TTF 子集**（脚本取 macOS 的
  `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`）；非嵌入 CID 字体会让 file-viewer
  的中文预览乱码（commit `094b863`）。所以 `samples/` 不要手改，改脚本重跑。
- `download_model.sh` / `fetch_file_viewer.sh` 下载的东西都 gitignore（`var/`），换机器要重跑。
- WebKit 兼容检查不在 `scripts/`，在 `tests/e2e/webkit/`（node + Playwright）。
