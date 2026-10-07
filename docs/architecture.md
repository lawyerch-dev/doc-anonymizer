# 架构与目录设计

**怎么用**看 [README](../README.md)，**不能违反的边界**看 [AGENTS.md](../AGENTS.md)，本文只解释
"为什么这么分层、这么摆目录"，并记录每次搬迁的动因。

## 一、分层：app → 引擎 → 契约

```
文件 ─► [抽取器 extractors] ─► Block(带定位)
     ─► [检测器 detectors]   ─► Detection(span/type/source)
     ─► [合并 resolve]       ─► 无重叠 span
     ─► [策略 strategies]    ─► 替换值(经 mapping 保证全文一致)
     ─► [回写 writers]       ─► 原格式产物 + manifest/mapping
```

| 层 | 目录/模块 | 职责 | 允许依赖 |
|---|---|---|---|
| 入口 | `cli.py`、`server.py` | 命令行 / 本地 HTTP | 下面所有 |
| 编排 | `pipeline.py`、`job.py`、`config.py`、`inventory.py`、`resources.py` | 串流程、账本、配置、自检、路径 | app 侧 + 引擎 |
| 领域 | `strategies.py`、`mapping.py`、`resolve.py`、`writers.py` | 替换策略、一致性、回写 | 契约 |
| 引擎 | `engines/`（`ocr.py`/`ocr_image.py`/`onnx_ner.py`/`llm/`） | 真正碰模型/推理库的部分 | **只有** `contract.py` |
| 契约 | `contract.py` | `Block`/`Span`/`Detection`/`Engine` ABC | 只有标准库 |

方向永远是从上往下。**引擎目录即边界**：`engines/` 下的任何文件都不许 import app 侧的东西，
由 `tests/test_architecture.py` 按目录机械检查（不是人工名单）。整块搬去别的项目 = 拷
`engines/` + `contract.py`。

## 二、目录现状

```
doc-anonymizer/
├── src/docanon/            代码(见上表); 布局路径集中在 resources.LAYOUT
├── apps/
│   ├── web/               零构建前端: index.html + app.css + app.js(由 server 直接发出去)
│   └── desktop/            Electrobun 壳(系统 WebView) + hutch.lock
├── configs/                配置(default / onnx / with_llm), 包外, 随资源根走
├── samples/                内置样例: Web 预设 + 测试数据(scripts/make_samples.py 生成)
├── scripts/                开发者脚本(见 scripts/README.md)
├── tests/                  pytest 测试 + tests/e2e/webkit(WebKit 兼容检查, node, 不进 pytest)
├── docs/                   本文件 / benchmarks.md / specs/(设计历史)
└── var/                    下载或构建得到的资产(gitignore): models 权重、vendor 预览包
```

## 三、五条硬边界（都有测试锁着，别绕过）

| 边界 | 锁在哪 | 违反的后果 |
|---|---|---|
| 引擎只认契约（可整块搬走） | `tests/test_architecture.py`（遍历 `engines/**`）+ `tests/test_engine_portability.py`（真的拷到别处导入一遍） | 引擎无法整块搬走 |
| 资源根可验证、布局只有一处真相 | `tests/test_resources.py`、`tests/test_layout.py` | 非 editable 安装下静默读到空配置 |
| 产物命名 `<全名>.redacted.<原扩展名>` + 保留子目录 | `tests/test_output_layout.py` | 同名文件互相覆盖 |
| 账本每文件原子落盘、`--resume` 要求产物仍在 | `tests/test_job.py` | Ctrl+C/崩溃丢记录，或把漏脱敏报成已处理 |
| PDF **命中页不留可提取文字**（未命中页原样保留） | `tests/test_pdf_output.py` | 给文字层盖黑块 = 原文仍可复制 = 没脱敏 |

共同的设计原则是**"少一层宁可报错，也不许静默"**：`prepare_detectors` 跑前预检、`ResourceRootError`、
`load_config` 读不到就抛、`manifest` 的 `ok|error|unsupported` 三态、`restore` 拒绝二进制产物。

## 四、关键决策记录

| 决策 | 理由 | 代价 |
|---|---|---|
| 前端零构建、`index.html + app.css + app.js` 三个静态件 | 无 node 构建链；预览包(file-viewer)是预构建产物，直接用；`app.js` 用 `@ts-check` + JSDoc 换编辑器的类型提示 | 没有打包/压缩，也没有真正的类型检查（等 DOM 复杂度上去再谈） |
| `configs/` 在包外 + `resources.LAYOUT` | 打包成桌面应用时资源与代码分开搬；模型/前端本来就进不了 wheel | 需要资源根概念；非 editable 安装必须显式报错 |
| **不做 wheel 自包含** | vendor 232MB、模型 GB 级，不该进包 | `pip install .` 到别处不可用（有明确报错 + `DOCANON_ROOT`） |
| 引擎放同包内的 `engines/` 目录，不拆独立发行包 | 第二个消费者还没出现；拆包要引入版本与发现机制，而 entry-points 的发现失败天然是静默降级 | 边界靠测试维持，不是靠包系统 |
| 可再生资产集中在 `var/` | "哪些是代码、哪些能删"一眼可辨；`git clean -xdf` 语义干净 | 唯一例外是 `apps/desktop/build/`（Hutch 的 `buildFolder` 只接受项目相对路径，不许 `..`） |
| **PDF 命中页整页栅格化**（不接受"保留文字层 + 盖黑块"） | 盖黑块不改变内容流，原文仍可复制/搜索 —— 那等于没脱敏；宁可牺牲该页的可编辑性 | 命中页不可再编辑、体积变大（已收窄到"只有命中的页"） |
| 不引入 lint / typecheck / CI | 单人本地工具、无远端可跑 CI；测试套件（76 项，含真实模型/OCR/浏览器检查）就是门禁，多一层工具链只增加维护面 | 靠约定而非工具挡小错；`AGENTS.md` 因此明写"别顺手加" |
| 桌面壳用 Electrobun | 系统 WebView，体积小一个数量级；Chromium 内核的 Electron 被弃 | WKWebView 的坑要自己趟（PDF 抖动当年的 Tauri 就死在这） |

## 五、搬迁历史（2026-10-05 → 10-07）

| 提交 | 做了什么 | 为什么 |
|---|---|---|
| `82dc18f` | 引擎/前端/壳分层：`config/`→`configs/`，前端移出 Python 包 → `apps/web` | 前端不是 Python；sdist 里不该混进 232MB vendor |
| `12a3d9b` | 引擎可移植化：`contract.py` + 注册表预检 + 进度缓存 + 资源根 | "整块搬走"与"少一层必须报错"两条原则落地 |
| `b4ca552` | `job.py` 账本：每文件原子落盘 + `--resume` | 几十页扫描件跑到一半崩掉不能白跑 |
| `22af2a5` | 资源根改为可验证解析；桌面壳定为 Electrobun（Electron 退场） | 非 editable 安装会静默读空配置；两个壳是纯负担 |
| `4b3e91b` | 引擎收进 `engines/`，边界改按目录机械检查 | 人工名单会漏：新增引擎文件完全不受检查（实测过） |
| `fea544b` | 引擎"可搬走"改为被验证的事实；`server.py` 拆成 `server/{__init__,routes,lifecycle}.py` | 承诺要能被跑出来；301 行的单文件混了三种关注点 |
| `75b6bfe` | 前端拆 `index.html` + `app.css` + `app.js`（仍零构建，`@ts-check` 换类型提示） | 327 行单文件里 HTML/CSS/JS 混在一起 |
| `8acfe7a` | PDF 只栅格化命中的页，未命中页保留矢量文字 | 整份变位图：49 页干净的也丢文字层、体积翻倍 |
| `0476003` | `resources.LAYOUT` 一张表 + 打包契约写进 pyproject | 布局知识原本散在 4 处，挪目录没有任何红灯 |
| `dc479e3` | `var/` 收 models + vendor | 5.9G/232MB 散在三个顶层，"哪些能删"要靠 .gitignore 反推 |
| `fb92745` | WebKit 兼容检查归位 `tests/e2e/webkit`；测试样板收敛到 `conftest.py` | 它测的是 Web UI 不是壳；样板抄了三遍 |

## 六、有意不做的三件事（不是欠债，是带理由的选择）

| 不做 | 理由 | 证据/兜底 |
|---|---|---|
| 把 `engines/` 拆成独立发行包（entry points 发现） | 第二个消费者还没出现；插件发现失败天然是静默降级，与"少一层必须报错"的原则冲突。整块搬走的能力**已经存在**，只是不额外发行 | `tests/test_engine_portability.py` 真的把它拷到别处导入一遍（带陷阱包，越界即炸）；真要发行时只加 `pyproject.toml` |
| 引入 lint / typecheck / CI | 单人本地工具、无远端；测试即门禁。真加 lint 会同时改掉 `AGENTS.md` 里"别顺手加"的约定 | 76 项测试覆盖边界/布局/产物/服务生命周期/浏览器端；`app.js` 用 `@ts-check` 拿编辑器提示，不引构建 |
| 让 PDF 产物"可选中/可编辑" | 保留文字层就意味着敏感原文仍可被复制/搜索，那是**泄漏不是特性** | 反过来说：命中页整页栅格化 + 无命中页保留，已由 `tests/test_pdf_output.py` 锁死 |

其余历史遗留（如 Electron/Tauri 壳、`apps/web/vendor` 散放、人工引擎名单）都已在本轮或前几轮清掉。
