[English](architecture.en.md) | 中文

# 架构与目录设计

**怎么用**看 [README](../README.md)，**不能违反的边界**看 [AGENTS.md](../AGENTS.md)，
本文解释"为什么这么分包、这么摆目录"，并记录每次搬迁的动因。

## 一、五包结构

```
packages/
├── docanon-contract/          引擎与 app 之间唯一的共享层: Block/Span/Detection/Engine ABC
│                              (只准标准库, 零运行时依赖)
├── docanon-engine-ocr/        OCR 引擎: RapidOCR 包装 + 图片/扫描页抽取(→ 文字 + bbox)
├── docanon-engine-ner-onnx/   ONNX NER 引擎: 编码器式中文 NER(标签→实体类型的词表由 app 传入)
├── docanon-engine-ner-llm/    LLM NER 引擎: llama-server(OpenAI 兼容)传输层 + 检测器
└── docanon-core/              app: 抽取/检测编排、脱敏与回写、账本、CLI、本地 Web
```

`packages/` 下还有一个 `ui`（JS 共享组件库），它不在这五个 Python 包与这条依赖方向之内。

依赖方向是单行道，**由包与 pyproject 共同锁死**（`tests/test_architecture.py`）：

```
core ──► engine-ocr ──┐
     ├─► engine-ner-onnx ──┼──► contract
     └─► engine-ner-llm ───┘
```

- 引擎包之间**互不依赖**，各自只依赖契约；整块搬走 = 拷"契约 + 那一个引擎包"
  （`tests/test_engine_portability.py` 真的拷到别处 import 一遍，另外两个包放成会抛异常的陷阱）。
- core 只许用引擎包的**公开面**（`from docanon_engine_x import Y`），不许伸手进 `...detector` 这类内部模块。
- 依赖归属跟着实现走：`numpy`/`tokenizers` 属于 ONNX 引擎，`rapidocr`/`onnxruntime`/`Pillow` 属于 OCR 引擎，
  `pyyaml`/`pypdfium2`/`python-docx`/`openpyxl`/`Pillow` 属于 core（回写要用）。
  以前它们混在一个 `[ocr]` extra 里，甚至有隐式依赖（numpy/tokenizers 靠 rapidocr 顺带装进来）。

### core 内部按流水线分层

```
docanon_core/
├── cli.py inventory.py          入口 / `docanon engines` 自检清单
├── config.py resources.py       配置与资源根(布局表 LAYOUT 是唯一真相)
├── extractors/                  抽取层: base(按扩展名路由) text_file pdf table
├── detectors/                   检测层: base(DETECTORS 注册表) rule dictionary
├── redaction/                   替换与回写: strategies mapping resolve writers
├── pipeline.py job.py           编排 / 账本(manifest+mapping, 原子落盘)
└── server/                      本地 Web: routes(答请求) lifecycle(sidecar 自杀)
```

## 二、仓库根（为什么只剩这些）

```
doc-anonymizer/
├── packages/
│   ├── docanon-*        五个 Python 包(见上); 每个包自带 tests/
│   └── ui/              共享组件包 @doc-anonymizer/ui: velora 组件 + 设计 token(网站与产品前端共同引用)
├── apps/
│   ├── web/             产品前端(Vite+React): src/ 源码 → dist/ 产物, docanon web 发 dist/
│   └── desktop/         Electrobun 壳(系统 WebView) + hutch.lock
├── configs/             运行期配置(default / onnx / llm) —— 随资源根走, 不进包
├── samples/             内置样例: Web 预设 + 测试数据(scripts/make_samples.py 生成)
├── scripts/             开发者脚本(见 scripts/README.md)
├── tests/               跨包测试: 包边界 + 可搬运性 + e2e/webkit
├── website/             官网 + 文档站: Astro 5 + Starlight, 静态输出 dist/
├── .agent/              给 agent 看的分类规范: AGENTS.md 是索引, rules/ 是细则
├── docs/                本文件 / benchmarks.md / specs/(设计历史)
├── var/                 本地可再生状态(gitignore): models 权重 / vendor 预览包 / out 默认产物 / pycache 字节码
├── package.json         前端工作区根 + **唯一命令入口**(npm run setup/dev/test/build/...)
├── package-lock.json    前端依赖锁(可复现安装)
├── pyproject.toml       Python 侧工作区根: 只有 pytest 配置(这里没有包, 也没有代码)
├── requirements-dev.txt 一条命令装好五个包(editable) + 测试依赖
├── conftest.py          共享 fixture(仓库根, 所有包的测试都能用)
└── 开源项目门面          LICENSE / CHANGELOG.md / CONTRIBUTING.md / .gitattributes
                          .github/ 里: SECURITY.md / CODE_OF_CONDUCT.md / issue 与 PR 模板
```

`configs/` 与 `samples/` 故意留在仓库根而不是塞进包：它们是**资源根**的内容（打包成桌面应用时
与代码分开搬），路径全部由 `resources.LAYOUT` 一张表管理。默认产物也落在 `var/out`，
所以"跑一次工具"不会在根目录留下垃圾。

## 三、开发与测试不需要启动桌面壳

日常就是 `npm run setup|dev|test`（命令含义见 [README](../README.md)）。
壳只是把同一套 Web UI 装进原生窗口，而壳里的渲染由 `tests/e2e/webkit/`（Playwright 的 WebKit 内核）
覆盖，所以改界面不必开窗口。

## 四、六条硬边界（都有测试锁着，别绕过）

| 边界 | 锁在哪 | 违反的后果 |
|---|---|---|
| 契约只标准库；引擎只依赖契约+自己；core 只用引擎公开面；pyproject 依赖与代码一致 | `tests/test_architecture.py` | 包边界烂掉，"整块搬走"不再成立 |
| 引擎能整块搬走 | `tests/test_engine_portability.py`（拷到只有契约+自己的环境里 import） | 引擎偷偷依赖 core，搬走即炸 |
| 资源根可验证、布局只有一处真相 | `packages/docanon-core/tests/test_{resources,layout}.py` | 非 editable 安装下静默读到空配置 |
| 产物命名 `<全名>.redacted.<原扩展名>` + 保留子目录；账本每文件原子落盘、`--resume` 要求产物仍在 | `test_output_layout.py`、`test_job.py` | 同名覆盖；崩溃丢记录；把漏脱敏报成已处理 |
| PDF 命中页不留可提取文字（未命中页原样保留） | `test_pdf_output.py`（[决策记录](../.agent/notes/implemented/architecture/2026-10-06-pdf-hit-pages-rasterized.md)） | 给文字层盖黑块 = 原文仍可复制 = 没脱敏 |
| **文档不与代码漂移**（路径、链接、测试文件名、AGENTS 里的测试数量） | `tests/test_docs.py` | 代码搬了文档还写旧的 —— 前后矛盾，读文档的人被带到沟里 |

共同原则：**"少一层宁可报错，也不许静默"**（`prepare_detectors` 预检、`ResourceRootError`、
`load_config` 读不到就抛、`manifest` 三态、`LLMError`、PDF 栅格化）。

## 五、关键决策记录（本项目的 ADR）

这一节就是本项目的架构决策记录：每条都写了**理由**和**代价**，也包括被否掉的方案。
故意**不**另开 docs/decisions/ 这层目录 —— 同一个决策有两个出处，早晚会互相矛盾
（这类漂移 `tests/test_docs.py` 抓不到，只能靠"只有一个真相"避免）。

| 决策 | 理由 | 代价 |
|---|---|---|
| **拆成五个包**（contract + core + 3 个引擎） | 依赖方向与"能搬走"由包系统表达，比"同包内的目录 + 测试约束"更硬；每个包的依赖就是它实现需要的 | 安装要多一条 `requirements-dev.txt`；跨包重构要改 pyproject |
| 引擎分三个而不是一个 | OCR / ONNX NER / LLM NER 的依赖与失败模式完全不同（一个吃 rapidocr，一个吃 onnxruntime，一个只是 HTTP）；分开后各自可单独安装、单独测试 | 包多一些 |
| 不用 entry points 发现引擎 | 发现失败天然是静默降级，与"少一层必须报错"冲突；core 显式 import 三个引擎，注册表显式登记 | 加引擎要改 core 的 pyproject 与注册表（有意） |
| 默认产物落 `var/out` | 跑一次工具不在仓库根留垃圾；`var/` 一条 gitignore 覆盖 | 与老文档/肌肉记忆里的 `-o out` 不同 |
| `configs/` `samples/` 留在根、不进包 | 它们是资源根的内容，打包时与代码分开搬；`resources.LAYOUT` 统一管理 | 需要资源根与 `DOCANON_ROOT` 概念 |
| **不做 wheel 自包含** | 前端 vendor 232MB、模型 GB 级，不该进包 | `pip install .` 到别处不可用（明确报错 + `DOCANON_ROOT`） |
| **前端改 Vite + React + TS**（构建期 node，运行期零 node；决策详情：[笔记](../.agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md)） | 复用 `packages/ui`（换栈不换外观）、有真类型检查与打包压缩 | 多一条构建链与 dist 前置依赖 |
| PDF 命中页整页栅格化 | 盖黑块不改变内容流，原文仍可复制/搜索 | 命中页不可再编辑（已收窄到"只有命中的页"） |
| 命令入口 = 仓库根的 npm scripts（`scripts/dev.sh` 退居实现层） | 前端本来就要 node：一键 `npm run dev` / `npm test` 比让人记 `./scripts/dev.sh <子命令>` 更好记；shell 逻辑留在 dev.sh，不塞进 package.json | 多一层包装（排查时仍可直接用 dev.sh 与底层命令） |
| 开发文档：`AGENTS.md` 只做索引，细则拆到 `.agent/rules/` | 160 行的「什么都塞」没人读完再动手；按主题拆开后改前端只读前端那篇 | 文档多一层跳转；靠守卫（AGENTS ≤80 行、每篇 ≤60 行、每篇都被索引）防膨胀 |
| 前端组件抽成共享包 `packages/ui`, 网站用 Astro + Starlight（决策详情：[共享包](../.agent/notes/implemented/architecture/2026-10-07-shared-ui-package.md) · [Astro 选型](../.agent/notes/implemented/architecture/2026-10-07-astro-starlight-for-website.md)） | velora(MIT shadcn 组件)是 React/Tailwind 4 的; 组件与 token 只放一份, `website/` 与产品前端(`apps/web`)引同一个包 —— **复用靠包, 不靠复制**。网站选 Starlight 是因为 搜索/TOC/上下页/多语言内置、依赖 241MB 与构建 0.7s 都比 Next 方案小一个量级(实测对比见 website/README.md) | 前端多了 npm workspaces 与构建链(仅构建期); 网站与产品 app 是两个框架(组件仍共享) |
| 桌面壳用 Electrobun | 系统 WebView，体积小一个数量级 | WKWebView 的坑自己趟（Tauri 就死在 PDF 抖动上） |

## 六、搬迁历史

| 提交 | 做了什么 | 为什么 |
|---|---|---|
| `82dc18f` | `config/`→`configs/`，前端移出 Python 包 → `apps/web` | 前端不是 Python；sdist 不该混进 232MB vendor |
| `12a3d9b` | 引擎可移植化：`contract.py` + 注册表预检 + 缓存 + 资源根 | "整块搬走"与"少一层必须报错"落地 |
| `b4ca552` | `job.py` 账本：每文件原子落盘 + `--resume` | 几十页扫描件跑到一半崩掉不能白跑 |
| `22af2a5` | 资源根可验证解析；桌面壳定为 Electrobun（Electron 退场） | 非 editable 会静默读空配置；两个壳是纯负担 |
| `4b3e91b` | 引擎收进 `engines/`，边界改按目录机械检查 | 人工名单会漏：新增引擎文件完全不受检查（实测过） |
| `0476003` | `resources.LAYOUT` 一张表 + 打包契约写进 pyproject | 布局知识原本散在 4 处，挪目录没有红灯 |
| `dc479e3` | `var/` 收 models + vendor | 5.9G/232MB 散在三个顶层，"哪些能删"靠反推 |
| `fb92745` | WebKit 兼容检查归位 `tests/e2e/webkit`；测试样板收敛 | 它测的是 Web UI 不是壳；样板抄了三遍 |
| `3866afe` | 文档拆 `docs/{architecture,benchmarks}.md` + `scripts/README.md` | README 职责变清楚 |
| `8acfe7a` | PDF 只栅格化命中的页 | 整份变位图：干净的页也丢文字层、体积翻倍 |
| `73cf1aa` | **拆成五包 monorepo**；测试按包分；默认产物落 `var/out` | 依赖方向由包表达；根目录只留"包 + 资源 + 工具" |
| `4a55f92` | 修掉 12 处文档矛盾 + 补 `tests/test_docs.py`；修 `bench_models.py` 扫错目录 | 代码搬了文档还写旧的；"别再矛盾"得靠测试而不是自觉 |

## 七、有意不做的三件事（不是欠债，是带理由的选择）

| 不做 | 理由 | 证据/兜底 |
|---|---|---|
| 把引擎发布到包索引、用 entry points 让第三方插拔 | 没有第三方消费者；发现失败是静默降级，与"少一层必须报错"冲突。**包已经是独立的**，缺的只是"发布" | `tests/test_engine_portability.py` 证明单个引擎包能独立拿走 |
| 引入 lint / typecheck / CI | 单人本地工具、无远端；测试即门禁。真加 lint 会同时改掉 `AGENTS.md` 里"别顺手加"的约定 | 全量测试覆盖包边界/可搬运/布局/产物/服务生命周期/浏览器端 |
| 让 PDF 产物"可选中/可编辑" | 保留文字层就意味着敏感原文仍可被复制/搜索 —— 那是泄漏不是特性 | 命中页栅格化 + 未命中页保留，由 `test_pdf_output.py` 锁死 |
