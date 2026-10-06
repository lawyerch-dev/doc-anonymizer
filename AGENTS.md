# doc-anonymizer 操作契约

日常开发只碰两处：`.venv` 里的 Python 引擎 `src/docanon/`，和零构建的单文件前端
`apps/web/index.html`。桌面壳只有一个（`apps/desktop/`，Electrobun + 系统 WebView），不是日常路径
（`apps/desktop/README.md` 明写「开发时不用它」）。

## 命令（一律在仓库根执行）

- 首次准备：`python3.12 -m venv .venv && .venv/bin/pip install -e '.[ocr,dev]'`
- 全量测试：`.venv/bin/python -m pytest -q`（55 项，约 3 秒）
- 单个测试：`.venv/bin/python -m pytest tests/test_pipeline.py::test_pipeline_masks_pii`
- CLI 脱敏：`.venv/bin/docanon run ./samples -o out -c configs/onnx.yaml`
- 大卷宗续跑（跳过已脱敏且产物仍在的）：同一条命令加 `--resume`
- 看这份配置实际加载了哪些引擎（含起不来的原因）：`.venv/bin/docanon engines -c configs/onnx.yaml`
- Web：`.venv/bin/docanon web -p 8000 -c configs/onnx.yaml`
- 仓库没有 lint、typecheck、CI、pre-commit。不要假定 `ruff`/`mypy`/`npm run lint` 存在，也不要顺手加。

## 三个会让结果失真的坑

- 测试必须用 `.venv/bin/python -m pytest`。PATH 上的 `pytest` 跑在 Homebrew Python 3.14 上，缺
  `rapidocr`，会静默 skip 掉 2 个扫描件测试并报 `15 passed, 2 skipped` —— OCR 回归根本测不出来。
  `pyproject.toml` 已把 `requires-python` 限到 `<3.14`，`docanon` 同理只在 `.venv/bin/` 里。
- 相对路径按**资源根**解析，不按 cwd：`-c` 的配置文件、`configs/*.yaml` 里的 `onnx.model_dirs` 都以仓库根
  为基准（打包后是 bundle 根，`DOCANON_ROOT` 可覆盖）—— 统一走 `src/docanon/resources.py`。
  命令行上的输入/输出路径仍按调用者 cwd。
  资源根是**逐级向上找**出来的（标记是 `configs/default.yaml`），不是用 `parents[N]` 猜的：找不到就抛
  `ResourceRootError` 让你设 `DOCANON_ROOT`。同样，`-c` 指向的文件、以及不带 `-c` 时的 `default.yaml`
  读不到都直接报错 —— 静默退化成空配置等于"一层引擎都没开"，而它看起来和"没启用"一模一样
  （`tests/test_resources.py` 锁这两条）。
- 不带 `-c` 走 `configs/default.yaml`，其中 `onnx_ner`/`llm_ner` 均为 `false`，只剩规则+词典：
  同一个 `samples/example.txt` 实测少掉 `PERSON` 与 `LOCATION`。Web 与桌面壳都用 `configs/onnx.yaml`。
  `configs/with_llm.yaml` 需先 `./scripts/serve_llm.sh` 把 llama-server 起到 :8080。

## 风险边界

- `mapping.json` 保存全部敏感原文，绝不与脱敏产物一起外发或提交。
- 输出目录不能位于输入目录内：下一次 run 会把上一次的 `.redacted.*` 当成新文档再脱敏一遍。
- 未脱敏不能报成已处理。新格式/新抽取器接入必须走 `manifest.json` 的 `ok|error|unsupported` 三态，
  并保留非零退出（见 `src/docanon/cli.py` 的 `EXIT_PARTIAL`）。依据是设计原则「召回优先（宁多勿漏）」。
- 加检测引擎＝在 `detectors/base.py` 的 `DETECTORS` 注册表里登记一行，配置文件用同名键打开。
  键名写错、或所有检测器都没开，都会立刻报错而不是静默少一层。引擎按配置指纹在进程内缓存，
  `build_detectors` 每进程只真正加载一次（11 个样例实测 8.20s→5.29s，ONNX 构造 22 次→2 次）。
- 开跑前 `prepare_detectors` 会对每个引擎调 `ready()`；任何引擎起不来就是退出码 1、连输出目录都不建
  （`docanon web` 同样拒绝启动）。所以**任何引擎或端点失败都必须抛错**，不许 `except: return []`——
  把「没答上」写成「零命中」是最坏的失败形态（`llm/client.py` 的 `LLMError` 就是这个边界）。
- 产物命名 `<源文件全名>.redacted.<原扩展名>` 且保留相对子目录，由 `tests/test_output_layout.py` 锁定
  （为的是防同名互相覆盖）。改命名等于改契约。
- 一个 `-o` 目录就是唯一真相：`manifest.json`/`mapping.json` 按源文件**累加**（同一 `source` 只更新它那一条）。
  分批跑就往同一个目录跑，不要新建 `out2/`、`out_mp2/` 这类平行目录，也不要预先清空它。
  `cmd_run` 退出码按合并后的清单算，所以历史 `error`/`unsupported` 记录会让它返回 `2` —— 那是提示，不是本次跑坏了。
- 账本的写入纪律（`src/docanon/job.py`）：**每处理完一个文件就落盘**，先写 `.tmp` 再 `os.replace`。
  改成"整批跑完再写"就等于让 Ctrl+C/崩溃丢掉已完成部分的原文与记录。`--resume` 判定"已脱敏"必须同时要求
  产物文件仍在；账本读不出来就拒绝执行（退出码 1、一个文件都不碰），不许静默当成空目录重来。
- 非目标：不接云端 API、不依赖 Ollama（`docs/specs/2026-10-05-doc-anonymizer-design.md` §6）。

## 改动前后

- `samples/` 由 `scripts/make_samples.py` 生成，不要手改。重新生成的 PDF 必须内嵌中文 TTF 子集
  （脚本取 macOS 的 `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`）；非嵌入 CID 字体会让
  file-viewer 的中文预览乱码（commit `094b863`）。
- 干净环境起 Web 前先 `./scripts/fetch_file_viewer.sh`；`apps/web/vendor/`（232MB）已 gitignore，
  缺它时预览区所有 `/file-viewer/*` 请求都 404。
- Web 后端关掉了 HTTP 访问日志（`server.py` 的 `log_message` 是空实现）。命中溯源看 `/api/anonymize`
  返回的 `trace`（`extractor`/`detectors`/`timing`/`detections`），前端「运行日志」弹窗消费的就是它。
- `models/`、`out*/`、`apps/web/vendor/` 均已 gitignore，提交里不要带上。
- 桌面壳（`apps/desktop/`，Electrobun）只在 `hutch electrobun dev` 里跑，日常不碰。它有三条实测出来的硬约束：
  项目根靠标记文件向上找（不许数 `..`，dev 产物在 `.app` 里）、sidecar 由 `DOCANON_EXIT_WITH_PARENT`
  父进程监视自尽（壳被强杀时 JS 收不了尸）、`/health` 带 pid 以免认错端口上的旧孤儿。
  细节见 `apps/desktop/README.md`，行为由 `tests/test_server.py` 锁定。

## 引擎可移植边界（`tests/test_architecture.py` 用 AST 锁死，别绕过）

- `contract.py` 是引擎与 app 之间唯一的共享层，只准 import 标准库。
- 引擎文件（`extractors/_ocr.py`、`extractors/ocr_image.py`、`detectors/onnx_ner.py`、
  `detectors/llm_ner.py`、`llm/client.py`）只准 import `docanon.contract` 和它自己那一个子包；
  `base`/`config`/`resources`/`pipeline`/`cli`/`server` 这些 app 侧模块一个都不许碰。
  方向永远是 **app → 引擎 → 契约**，反了就没法整块搬走。
- 实体词表属于 app：标签→`PERSON/ORG/...` 在 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP`，
  `OnnxNERDetector(model_dir, entity_map)` 把它当必填参数收，`llm_ner` 只认 `_VALID_TYPES`。别把实体名写回引擎。
- 引擎参数也属于引擎：`LLMConfig` 住在 `llm/client.py`，`config.py` 反过来 import 它。
- 新引擎要实现 `capabilities()`（实际能识别什么）和 `ready()`（起不来给原因）——`docanon engines` 与跑前
  预检都吃这两个自述；缺任一方法时基类的默认值会让该引擎在清单里显示"什么都不认识"，这是故意的。
- 真要拆成独立 pip 包（entry points 发现）等第二个项目出现再做，届时只加 `pyproject.toml`；现在别预拆。

## 深度文档（按需读，不要抄进本文件）

- 架构与模型选型：`docs/specs/2026-10-05-doc-anonymizer-design.md`
- 已知限制（漏脱敏、还原失败的权威清单）：`README.md`「已知限制」段
