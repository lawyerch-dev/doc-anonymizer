# doc-anonymizer 操作契约

日常开发只碰两处：`.venv` 里的 Python 引擎 `src/docanon/`，和零构建的前端
`apps/web/`（`index.html` + `app.css` + `app.js`，由 `docanon web` 直接发出去，无 node 构建链）。
桌面壳只有一个（`apps/desktop/`，Electrobun + 系统 WebView），不是日常路径（`apps/desktop/README.md`
明写「开发时不用它」）。

## 命令（一律在仓库根执行）

- 首次准备：`python3.12 -m venv .venv && .venv/bin/pip install -e '.[ocr,dev]'`
- 全量测试：`.venv/bin/python -m pytest -q`（76 项，约 4 秒）
- 单个测试：`.venv/bin/python -m pytest tests/test_pipeline.py::test_pipeline_masks_pii`
- CLI 脱敏：`.venv/bin/docanon run ./samples -o out -c configs/onnx.yaml`
- 大卷宗续跑（跳过已脱敏且产物仍在的）：同一条命令加 `--resume`
- 看这份配置实际加载了哪些引擎（含起不来的原因）：`.venv/bin/docanon engines -c configs/onnx.yaml`
- 还原（**只吃文本产物**）：`.venv/bin/docanon restore out/sample.md.redacted.md --mapping out/mapping.json`
- Web：`.venv/bin/docanon web -p 8000 -c configs/onnx.yaml`
- 仓库没有 lint、typecheck、CI、pre-commit。不要假定 `ruff`/`mypy`/`npm run lint` 存在，也不要顺手加。

## 三个会让结果失真的坑

- 测试必须用 `.venv/bin/python -m pytest`。PATH 上的 `pytest` 跑在 Homebrew Python 3.14 上，缺
  `rapidocr`，会静默 skip 掉 2 个扫描件测试并报 `15 passed, 2 skipped` —— OCR 回归根本测不出来。
  `pyproject.toml` 已把 `requires-python` 限到 `<3.14`，`docanon` 同理只在 `.venv/bin/` 里。
- 相对路径按**资源根**解析，不按 cwd：`-c` 的配置文件、`configs/*.yaml` 里的 `onnx.model_dirs` 都以仓库根
  为基准（打包后是 bundle 根，`DOCANON_ROOT` 可覆盖）—— 统一走 `src/docanon/resources.py`。
  命令行上的输入/输出路径仍按调用者 cwd。
  **布局只有一处真相**：`resources.LAYOUT`（键→相对路径）。要挪目录就改这张表，`tests/test_layout.py`
  会立刻报出哪里对不上；访问器（`config_path`/`web_index`/`vendor_dir`/`samples_dir`/`models_dir`）
  一律走 `path(key)`，不许再自己拼路径。
  资源根是**逐级向上找**出来的（标记是 `configs/default.yaml`），不是用 `parents[N]` 猜的：找不到就抛
  `ResourceRootError` 让你设 `DOCANON_ROOT`。同样，`-c` 指向的文件、以及不带 `-c` 时的 `default.yaml`
  读不到都直接报错 —— 静默退化成空配置等于"一层引擎都没开"，而它看起来和"没启用"一模一样
  （`tests/test_resources.py` 锁这两条）。
- **部署契约**（写在 `pyproject.toml` 里）：只支持 editable 安装与打包根两种形态，**不做 wheel 自包含**
  —— 前端 vendor 232MB、模型 GB 级，本来就不该进包。
- 不带 `-c` 走 `configs/default.yaml`，其中 `onnx_ner`/`llm_ner` 均为 `false`，只剩规则+词典：
  同一个 `samples/example.txt` 实测少掉 `PERSON` 与 `LOCATION`。桌面壳固定用 `configs/onnx.yaml`，
  `docanon web` 要自己带 `-c`。`configs/with_llm.yaml` 需先 `./scripts/serve_llm.sh` 把 llama-server 起到 :8080。

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
- `restore` 只吃 UTF-8 文本产物（txt/md/csv）。`remove` 策略的替换值是**空串**，不是可定位的锚点：
  它只进正向表，绝不进 `MappingStore._reverse`，还原走 `restorable_items()`（过滤空键）。
  谁把空串塞回反向表，`str.replace("")` 就会把原文插到每个字符之间——还原动作反而把敏感信息撒满全篇。
  回归测试：`tests/test_restore.py`。
- **命中敏感信息的 PDF 页必须整页栅格化**（文字层消失）。给文字层盖黑块 = 原文仍可复制/搜索 =
  没脱敏，这条是安全保证不是偷懒；没命中的页原样保留矢量文字与体积。`tests/test_pdf_output.py` 锁死，
  README「已知限制」对用户解释同一件事。
- 非目标：不接云端 API、不依赖 Ollama（`docs/specs/2026-10-05-doc-anonymizer-design.md` §6）；
  也不引入 lint/typecheck/CI（单人本地工具，测试即门禁，理由见 `docs/architecture.md` §六）。

## 改动前后

- Web UI 的 WebKit 兼容检查在 `tests/e2e/webkit/`（node + Playwright，**不进 pytest**；pytest 的
  默认 `norecursedirs` 会跳过那里的 `node_modules`）。壳用的就是系统 WebView，改了预览相关的东西先跑它：
  `DOCANON_URL=http://127.0.0.1:8803 [PRESET=sample_text.pdf] node webkit-check.mjs`。
- `samples/` 由 `scripts/make_samples.py` 生成，不要手改。重新生成的 PDF 必须内嵌中文 TTF 子集
  （脚本取 macOS 的 `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`）；非嵌入 CID 字体会让
  file-viewer 的中文预览乱码（commit `094b863`）。
- 干净环境起 Web 前先 `./scripts/fetch_file_viewer.sh`；`var/vendor/`（232MB）已 gitignore，
  缺它时预览区所有 `/file-viewer/*` 请求都 404。
- Web 后端关掉了 HTTP 访问日志（`server/routes.py` 的 `log_message` 是空实现）。命中溯源看 `/api/anonymize`
  返回的 `trace`（`extractor`/`detectors`/`timing`/`detections`），前端「运行日志」弹窗消费的就是它。
- **可再生资产都在 `var/`**（`var/models` 权重、`var/vendor` 预览包；gitignore 一条 `var/` 覆盖），
  产物目录由 `-o` 决定（默认 `out/`，同样 gitignore）。唯一例外是壳的 `apps/desktop/build/`：
  Hutch 的 `buildFolder` 只接受项目相对路径、不许 `..` 跳出，所以它留在壳目录下（已 gitignore）。
- 桌面壳（`apps/desktop/`，Electrobun）只在 `hutch electrobun dev` 里跑，日常不碰。它有三条实测出来的硬约束：
  项目根靠标记文件向上找（不许数 `..`，dev 产物在 `.app` 里）、sidecar 由 `DOCANON_EXIT_WITH_PARENT`
  父进程监视自尽（壳被强杀时 JS 收不了尸）、`/health` 带 pid 以免认错端口上的旧孤儿。
  细节见 `apps/desktop/README.md`，行为由 `tests/test_server.py` 锁定。

## 引擎可移植边界（**目录即边界**，`tests/test_architecture.py` 用 AST 锁死）

- `src/docanon/engines/` 下的一切只准 import `docanon.contract` 与 `docanon.engines.*`。
  规则按**目录机械遍历**，新加引擎文件自动纳入 —— 旧写法是人工维护 5 个文件的名单，
  新加的引擎文件完全不受检查（实测：往 `detectors/` 扔一个 `from .. import config` 的文件，旧测试照样全绿）。
- `contract.py` 是两边唯一的共享层，只准 import 标准库。
- 方向永远是 **app → 引擎 → 契约**：app 侧（`config.py`、`detectors/base.py`、`extractors/base.py`）
  可以 import 引擎，引擎反过来一个都不许碰。整块搬走 = 拷 `engines/` + `contract.py`。
- 实体词表属于 app：标签→`PERSON/ORG/...` 在 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP`，
  `OnnxNERDetector(model_dir, entity_map)` 把它当必填参数收，`llm_ner` 只认 `_VALID_TYPES`。别把实体名写回引擎。
- 引擎参数也属于引擎：`LLMConfig` 住在 `engines/llm/client.py`，`config.py` 反过来 import 它。
- 新引擎要实现 `capabilities()`（实际能识别什么）和 `ready()`（起不来给原因）——`docanon engines` 与跑前
  预检都吃这两个自述；缺任一方法时基类的默认值会让该引擎在清单里显示"什么都不认识"，这是故意的。
- `docanon engines` 的实现住在 `inventory.py`（**不是** `engines.py`：包会遮蔽同名模块，两个不能并存）。
- 真要拆成独立 pip 包（entry points 发现）等第二个项目出现再做，届时只加 `pyproject.toml`；现在别预拆。

## 文档地图（改行为时一起改）

| 文件 | 管什么 | 权威性 |
|---|---|---|
| `README.md` | 使用者说明书：命令、产物与命名契约、支持范围、已知限制、Web 接口、桌面壳入口、文档导航 | 现状权威 |
| `AGENTS.md`（本文件） | 操作契约：不能违反的边界、命令、坑 | 现状权威 |
| `docs/architecture.md` | 分层与目录设计的**为什么**、五条硬边界、决策记录、搬迁历史 | 解释性，与代码同步 |
| `docs/benchmarks.md` | 模型选型与基准数字（ONNX vs LLM、各 GGUF 对比） | 实测记录 |
| `scripts/README.md` | 六个脚本各干什么、依赖、用法 | 现状权威 |
| `apps/desktop/README.md` | 桌面壳的运行方式与三条实测约束 | 现状权威 |
| `docs/specs/2026-10-05-*.md` | 设计决策的历史记录（选型与理由）+ §10 后续变更 | 历史记录，现状以本文件与 README 为准 |

- 改行为 → 同步 README 的「产物 / 已知限制 / Web 接口」段与对应测试；改边界 → 改本文件。
- 写进 README 的每条命令都要真跑一遍再说它成立，不许写"理论上"。
- **能力边界不要手写进文档**（哪些引擎认识哪些实体、起不起得来），让 `docanon engines` 自己报——
  写死的清单一定会漂移。

## 深度文档（按需读，不要抄进本文件）

- 架构与目录设计、决策与搬迁历史：`docs/architecture.md`
- 模型选型与基准：`docs/benchmarks.md`
- 最初的设计方案（历史记录）：`docs/specs/2026-10-05-doc-anonymizer-design.md`
- 已知限制（漏脱敏、还原失败的权威清单）：`README.md`「已知限制」段
