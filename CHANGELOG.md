# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，
变更记录格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Changed

- **命中统计 / 设置表的类型名改成中文**：`PHONE`、`ID_CARD`、`USCC`… 这类代码对非技术用户不友好。
  统一走 `apps/web/src/lib/formats.ts` 的一张 `ENTITY_LABELS` 映射（电话 / 身份证 / 统一社会信用代码…），
  鼠标悬停在类型上仍能看到原始代码（方便对日志与配置排查）。
  清单按**引擎的真实产出**登记：规则层 `detectors/rule.py` 的 PATTERNS、词典层固定给的 `CUSTOM`、
  ONNX 层经 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP` 映射后的类型（含 gyr66 的 `POSITION`）、兜底 `DEFAULT`。
  **没登记过的标签照原样显示代码**，不猜也不隐藏 —— 用户可以在配置里自定义 `onnx.entity_map`，
  那时会冒出什么标签我们并不知道，编一个中文名比显示代码更糟。
- **选中文档改为红色选中态**：文档列表里当前选中的那一项改成实心红底 + 白字（暗色下自动切成浅红底 + 深字），
  原先只是浅灰底 + 深色描边，不够醒目。为此在 `apps/web/src/styles.css` 新增一对**产品专属** token
  `--selected` / `--selected-foreground`：没有复用 kit 的 `--destructive`（那个红已被错误条与
  「版式可能被重排」警告占用，两种含义同色会互相干扰），也没放进 `packages/ui`（这是产品语义，
  不该让共享 kit 认识它）。
- **脱敏设置改为弹窗**：产品界面的口径（L1）/ 逐类型策略与自定义词典（L2）/ 检测引擎（L3）从左栏搬进
  右侧设置弹窗，入口是页头「⚙ 设置」按钮（紧邻主题切换按钮）；有未保存改动时按钮带 `•`，当前口径在它的
  悬停提示里。页头同时收敛为一行「设置 · 运行日志 · 明暗」——原先单独占一行的「未选择文档」状态行与
  左栏「口径」摘要行都去掉了；原来的命中合计 / 耗时 / 「已由 `.doc` 转换，版式可能被重排」折进
  「命中统计」卡（换格式警告不能随状态行一起消失）。
  顺带修掉一处会丢数据的隐患：词典 / LLM 地址 / LLM 模型名原先是**非受控 + `onBlur` 提交**，弹窗一关
  组件即卸载、`onBlur` 不触发，刚打的字会丢 —— 改成受控提交（词典保留一份本地草稿，否则
  `split/filter` 会把刚输入的分隔符当场吃掉）。弹窗复用共享库的 `primitives/sheet`（base-ui Dialog），
  **未新增依赖**；后端 API 与 E2E 依赖的 DOM 钩子（`.preset` `#run` `#paneSrc` `#paneOut` `#stats`）不变。
- **产品界面重写为 Vite + React + TS**：`apps/web/` 从零构建手写件（`index.html`+`app.css`+`app.js`）
  迁到 Vite 6 + React 19 + Tailwind 4，**复用**共享组件库 `@doc-anonymizer/ui`（velora + shadcn 基础件 +
  设计 token）—— 外观与官网不再分叉。顺带重排布局（选文档在左、原文/脱敏后对照在右）、补暗色与
  空/加载态。产物落 `apps/web/dist`（gitignore），`resources.LAYOUT["web"]` 随之改指 `dist`，
  `docanon web` 仍只发静态文件（**运行期零 node、全离线**不变）；API 一字未改。
  新增 `npm run build:web` / `dev:backend`，`npm run dev` 改为"后端 + Vite dev server 并发 + 六条前缀代理"
  （`/api` `/samples` `/uploads` `/outputs` `/file-viewer` `/health`；开发看 :5173，后端 :8000 只是代理目标）。
  设计与决策：[设计](docs/specs/2026-10-09-web-ui-vite-migration-design.md) ·
  [笔记](.agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md)。
- **默认脱敏口径改为 `**`**：新增 `redact` 策略（把整段原文盖成 `**`），人名/机构/自定义词/兜底类型默认走它，
  不再生成"像真的假名/假公司"——此前的 `华信集团` 式假名会让人误以为没脱敏。`pseudonym`（可信假名）
  改为**显式配置才用**。`configs/{default,onnx,llm}.yaml` 的策略词表已同步。

### Added

- **Web 分层脱敏配置**：Web 的"口径"从"选一个 `configs/*.yaml`"升级为**三层渐进披露** ——
  L1 口径（内置预设只读 + 我的配置）→ L2 逐类型策略 + 自定义词典 → L3 检测器/模型。新增
  `GET /api/configs`（列内置+用户、标当前）· `GET /api/configs/{ref}` · `PUT`/`DELETE /api/configs/{name}`
  （内置拒改/拒删）· `GET /api/configs/{name}/export` · `POST /api/configs/import` · `GET /api/models`；
  `/api/anonymize` 的 `config` 可为配置名或**内联对象**（改完即测，满意再存）。用户配置原子写入
  `var/configs/<name>.yaml`（与内置同 schema，复用 `load_config`）；运行期 `prepare_detectors` 预检，
  缺引擎返回 400 + 原因（不静默少一层）。设计与决策：
  [设计](docs/specs/2026-10-08-redaction-config-design.md) ·
  [笔记](.agent/notes/implemented/feature/2026-10-08-web-redaction-config.md)。
- **旧版 Office（`.doc`/`.xls`/`.wps`）自动转换**：抽取层借 LibreOffice 先转成 `.docx`/`.xlsx` 再脱敏，
  soffice 走"系统优先 → `var/libreoffice`（`scripts/fetch_libreoffice.sh`）"。产物的格式因此改变，
  账本（`converted`/`source_suffix`/`output_format`）、CLI 与 Web `trace` 都会标明"版式可能被重排"；
  缺 LibreOffice 时记 `unsupported`（退出码 2，带可操作 reason）。开关 `legacy_convert`（默认 `true`）。
  推翻了"旧格式一律手工前置转换"的旧约定；设计与理由见
  [`docs/specs/2026-10-08-legacy-office-conversion-design.md`](docs/specs/2026-10-08-legacy-office-conversion-design.md)。
- **`configs/legal.yaml`（法律文书交付件）+ `keep` 策略**。实测：用原先推荐的 `configs/onnx.yaml` 跑一份
  判决书式的材料，`北京市朝阳区人民法院` 被换成假公司名、`审判员`/`书记员`/`委托诉讼代理人` 被抹成
  `<POSITION_n>`、判决日期 `二〇二四年十月八日` 被当成生日抹掉 —— **材料交不出去，得返工**；
  而交付场景真正要抹的是身份证/银行卡/手机/住址这类标识与联系方式。所以：
  - 新增策略 **`keep`**（这类命中不动，只留溯源、不算进命中数）—— 没有它，配置只能表达"抹成什么"，
    表达不了"别碰它"（没列出的类型会被 `DEFAULT` 兜住一起抹掉）；
  - 新增 `configs/legal.yaml`：只抹标识与联系方式，机构/人名/角色/日期/金额/统一社会信用代码全部 `keep`，
    `onnx.entity_map` 只映射地址（其余标签引擎直接忽略，也就不可能产出可替换的人名机构）；
  - Web「运行日志」把"识别到但按配置保留"的条数单独列出（否则用户看见产物里留着金额，会以为是漏检）。
  回归测试：`test_legal_preset.py`（含"配置层面不许出现能产出人名/机构/角色/生日的标签"这一条）。
- **双语文档**：产品层四篇（README / 快速上手 / 架构 / 贡献指南）各有英文版 `<名字>.en.md`，
  站点变成中英双语（中文在根路径、英文在 `/en/`，Starlight 语言切换器 + 侧栏标签双语 + 缺译页面自动回退）。
  加**配对门禁** `test_bilingual_pages_are_paired_and_fresh`：英文版必须存在、能互相切回，
  且译文基线哈希（`en_hash` = 翻译时中文源的 sha256）与中文源一致 —— 改了中文忘改英文就红。
  维护步骤见 [`docs/cookbook/maintaining-bilingual-docs.md`](docs/cookbook/maintaining-bilingual-docs.md)。
- **仓库门面补全**：About 里设了在线文档地址（description 也带上），README 顶部加 docs 徽章与
  「在线文档 / 快速上手 / 参与开发 / 安全问题 / English」导航行。
- **落地页清理**：去掉当初验证组件库用的演示区块，文案抽到 `website/src/lib/landing-copy.ts`
  （中英各一份，组件只有一套），落地页也有 `/en/` 英文版。


- **反假绿门禁**：`npm run test:strict`（`DOCANON_REQUIRE_ENGINES=1`）声明"环境齐备"后，
  **任何 skip 都算失败**，并在终端点名是哪几条、为什么跳 —— 引擎测试缺模型时会 skip，
  否则"全绿"可能只是"引擎一次都没跑"。门禁自身有测试（`test_false_green_gate_fails_on_skips`）。
- **最小检查集**：`npm run check:scope` 按改动范围（committed / 工作区 / 未跟踪）算出该跑哪几条；
  跨层契约改动与无法归类的路径一律回到全量 `npm test`；没有自动化覆盖的目录（`apps/web`、`apps/desktop`）
  会明说要手工验证。配推送前手册 [`.agent/skills/before-you-push/SKILL.md`](.agent/skills/before-you-push/SKILL.md)，
  脚本自身有测试（`tests/test_check_scope.py`）。
- **事故复盘层** `.agent/postmortem/`：与"决策笔记"分工 —— 复盘写"漏到线上的东西为什么没兜住、补了什么护栏"，
  准入条件是隐蔽 + 系统性 + 重学成本高（三者都要）；门禁锁路径编号、执行摘要、根因、护栏与 README 索引。
  第一篇 [0001（Tailwind 类名被静默摇掉）](.agent/postmortem/0001-tailwind-source-dropped-classes.md)
  由 `notes/bug-fix` 改判而来 —— 笔记记决策，复盘记失败。

- **文档站自动部署（仓库唯一的 CI）**：`.github/workflows/deploy-website.yml` —— push `main` 时先跑门禁
  （文档漂移 + 包边界 + 组件库检查 + 站点构建）再发布 GitHub Pages。
- **网站支持子路径部署**：站内链接改走 `website/src/lib/site.ts` 的 `url()`（`SITE_BASE` → `base`、
  `SITE_URL` → sitemap）；新增两条守卫（禁止手写 `href="/…"`、部署 workflow 必须真跑门禁并发布 `website/dist`）。
  首次就抓到 workflow 里一个真实的 YAML 语法错（`name:` 里带冒号）。
- **场景操作指引** `docs/cookbook/`（评审改动 / 排查问题 / 构建部署网站）+ `docs/AGENTS.md`；
  文档站自动收录为新分组「操作指引」。

### Changed

- **共享组件库搬到 `packages/ui`**（原 `apps/ui`）。目录语义按通用 monorepo 规约定死：
  `packages/` = 被引用的库、`apps/` = 跑起来的东西 —— 所以 `packages/` 不再等于"Python 五包"，
  Python 侧改用 `packages/docanon-*` 指代。同批改掉 npm workspaces、`website` 的 Tailwind `@source`
  与内容清单、守卫测试里的硬编码路径，以及 README/CONTRIBUTING/规则/架构文档中英两侧。
  历史记录（决策笔记、事故复盘、本文件上方旧条目）按"记录类允许旧名字"保留。

- **借鉴 DeepSeek Harness 的规范与流程**（同一套里我们只取适合小仓库的部分）：
  - **决策/修复笔记**：`.agent/notes/{状态}/{类别}/日期-主题.md`（状态 `proposed|implemented|rejected|archived`、
    类别封闭集合），文件内 `Status:` 与目录交叉校验；**不建索引文件**，靠相对链接从架构表/规则里指过来。
  - **操作手册**：`.agent/skills/<名字>/SKILL.md`（自描述 frontmatter + 步骤 + 验证命令）——
    加检测器 / 加引擎包 / 发版本。
  - **每目录 `AGENTS.md`**：五个包各自一份本地约束（harness 会按 root→cwd 自动加载）。
  - 四条对应门禁进 `tests/test_docs.py`；文档站自动发现这三类内容（新增「决策记录/操作手册/包」三组，共 37 页）。
  - 有意**没搬**：双语文档（本仓库全中文）、CI/lefthook（测试即门禁）、笔记归档流程（规模还没到）。

- **文档审计**：修掉搬家后遗留的旧路径（`website/README.md` 还写着自己叫 `apps/website`、还在用
  `./scripts/dev.sh website`；架构决策记录指向旧文件），文档站补两页开发文档（组件库、官网/文档站）。
- **命令入口统一成 npm scripts**（仓库根 `package.json`）：`npm run setup` / `dev` / `dev:website` /
  `dev:desktop` / `test` / `build` / `cli` / `engines` / `models` / `doctor`。
  `scripts/dev.sh` 退居**实现层**（被 npm scripts 调用，仍可直接用）。
  根目录同时把 `SECURITY.md`、`CODE_OF_CONDUCT.md` 收进 `.github/`（GitHub 同样识别）。

- **文档信息架构**：`AGENTS.md` 从 160 行的"什么都塞"改成 51 行的**入口与索引**
  （六条不可违反 + 按主题的表），细则按主题拆到 `.agent/rules/`（9 篇：命令 / 包 / 资源 / 产物 /
  安全 / 测试 / 前端 / 文档 / 环境）。守卫：`AGENTS.md` ≤ 80 行、每篇 rule ≤ 60 行、每篇都必须被
  `AGENTS.md` 索引到 —— 不然又会长回去。
- **官网/文档站移到仓库根**：`apps/website/` → `website/`（它是项目门面，不是"某个 app"），
  同时把 9 篇契约细则也接进站点内容清单，站上可直接浏览（交叉链接自动改写成站内路由）。

### Added

- **共享组件库装全**：`apps/ui` 从"我们页面用到的那 6 个"补成 velora 完整库 ——
  **100 个组件 + 31 个区块 + 9 个 shadcn 基础件**（`registry.lock.json` 是 131 项的源头快照）。
  导入规范化成相对路径（消费方不必配 `@/` 别名），主题 token/keyframes 合进 `theme.css`；
  文档站多一页**组件库总览**（由 `apps/ui/src/manifest.json` 渲染，131 条带说明与用法）。

- **官网与文档站**：`apps/website/`（**Astro 5 + Starlight** + Tailwind CSS 4）——搜索/TOC/上下页/多语言
  内置，静态输出 `dist/`；内容按 `content-manifest.json` 从仓库 markdown 同步（源仍是那些 .md），
  `./scripts/dev.sh website` 起开发服务器。选型对比（依赖 241M vs Next 537M、构建 0.7s vs 3–4s、
  内置搜索 vs 手写）见 [website/README.md](website/README.md)。
- **共享组件包**：`apps/ui/`（`@doc-anonymizer/ui`，npm workspaces）—— velora 组件与设计 token
  只放一份，网站与将来的产品前端共用（[velora-ui](https://github.com/ColorlibHQ/velora-ui)，MIT）。

### Fixed

- **docx 超链接里的敏感信息漏脱敏、并把旁边的字改错**（用户可见的漏检 + 数据损坏，manifest 却报 `ok`）。
  `paragraph.text` 含超链接里的文字而 `paragraph.runs` 不含，抽取与回写各算一套字符偏移 ——
  实测 `B 行: 邮箱 a@b.com 联系电话 13800001111` 会变成
  `B 行: 邮箱 a@b.coma***@b.com380000138****1111`：邮箱原样留着，替换值插到别的字上。
  现在抽取与回写共用一套遍历（`packages/docanon-core/src/docanon_core/docx_walk.py`），
  段落定位失败直接抛错；本段被替换过的原文同时从 `w:instrText` 与超链接目标（`mailto:`/URL）里抹掉。
  同批修掉的同类漏检：**内容控件 `w:sdt`**、**嵌套表格**（`doc.tables` 只认顶层）、**修订插入 `w:ins`**、
  **简单域 `w:fldSimple`**。新增 `test_docx_output.py`（8 条断言型用例，改动前 7 条是红的）——
  此前 docx 回写路径**零测试**，这是它能潜伏至今的原因。
- **规则层补三类中文证件**：固定电话（并入 `PHONE`）、护照（`PASSPORT`）、车牌（`PLATE`）——
  实测 `010-87654321` / `E12345678` / `京A12345` 在之前的配置下全部漏过。
- 已知限制写准：docx 的页眉/页脚/脚注/文本框仍不抽取，**文档属性（作者名等）也不处理**（实测属性会原样留下），
  只在链接目标里出现的敏感值识别不到；`.doc`/`.xls` 的手工转换路径写进 cookbook（含实测命令与注意事项）。


## [0.1.0] — 2026-10-07

首个可用版本：CLI + Web + 桌面壳三件套，三条检测路线（规则/词典、ONNX NER、本地大模型 NER），
八种输入格式，产物保留原格式并可还原。

### Added

- **抽取**：txt/md、docx（正文段落 + 表格单元格）、pdf（文字层按 charbox、扫描页走 OCR）、
  图片（png/jpg/tiff/webp）、xlsx/csv。
- **检测**：`rule`（身份证/手机/银行卡/邮箱/IP/统一社会信用代码/密钥/金额）、`dictionary`（自定义敏感词）、
  `onnx_ner`（中文 NER，实测 100% 召回 / 34ms / 无需 server）、`llm_ner`（本地 `llama-server`）。
- **脱敏策略**：`pseudonym`（同类同实体固定假名）/ `placeholder` / `mask` / `remove`，按实体类型配置。
- **产物**：docx 按 run 回写、xlsx/csv 改写单元格、pdf 与图片按坐标涂黑；
  命名 `<源文件全名>.redacted.<原扩展名>` 且保留相对目录。
- **账本**：`manifest.json`（`ok`/`error`/`unsupported` 三态）+ `mapping.json`（原文↔替换值，可还原）；
  每处理完一个文件就原子落盘，`run --resume` 可续跑（要求产物仍在）。
- **CLI**：`run` / `restore` / `engines` / `web`，退出码 `0|1|2` 区分"全部完成/输入有误/有文件没产出"。
- **引擎自检**：`docanon engines` 列出每个引擎的可用性与实际能力（`capabilities()`/`ready()` 自述）。
- **Web 界面**：选内置示例或上传 → file-viewer 预览原文 → 一键脱敏 → 同查看器看脱敏件；
  命中统计与逐条溯源（`/api/anonymize` 返回 `trace`）。
- **桌面壳**：Electrobun（系统 WebView）+ Python sidecar。
- **文档**：快速上手、架构与目录设计、基准与选型、贡献指南、安全策略、更新日志。
- **一条命令起步**：`scripts/dev.sh`（装环境 / 起 Web / 起桌面壳 / 起文档站 / 跑测试 / 取模型 / 环境自检）与
  `scripts/download_onnx_models.sh`（官方 HF 不可达时默认走 `hf-mirror.com`，`HF_ENDPOINT` 可换）。

### Changed

- 代码拆成五个包（`packages/`）：`docanon-contract` + 三个引擎包 + `docanon-core`；
  依赖方向由包与 `pyproject.toml` 机械检查（`tests/test_architecture.py`）。
- 配置改名 `configs/with_llm.yaml` → `configs/llm.yaml`；默认产物目录 `out/` → `var/out`。
- 可再生资产（模型权重、预览资源、产物、字节码缓存）统一收进 `var/`（一条 gitignore 覆盖）。
- 布局路径收敛到 `resources.LAYOUT` 一张表（挪目录只改一处，有测试盯着）。
- 前端从单文件拆成 `index.html` + `app.css` + `app.js`（仍零构建）。
- 安装从 `pip install -e '.[ocr,dev]'` 改为 `./scripts/setup_dev.sh` / `requirements-dev.txt`。

### Fixed

- **`restore` 遇 `remove` 策略会把原文撒满全篇**：空替换值进了反向表，`str.replace("")` 把原文插到
  每个字符之间。现在空串只进正向表，还原统一走 `restorable_items()`，并对无法还原的条目给出提示。
- **Web 请求路径没有 unquote**：中文文件名的上传件在预览/下载处一律 404（接口自己发的 URL 就是中文路径）。
- 桌面壳在 dev 构建下拿系统 `python3` 起后端（`import.meta.dir` 指进 `.app` 内部）；改为按标记文件
  向上找项目根，找不到就报错退出。
- 壳被强杀时后端孤儿化占住端口：新增 `DOCANON_EXIT_WITH_PARENT` 父进程监视，sidecar 自己了断。
- 端口上蹲着旧孤儿时壳会开出一个"假窗口"：`/health` 现在带 pid，壳只认自己拉起的后端。
- `bench_models.py` 扫描已搬走的 `models/`（一个模型都找不到）；bench 脚本往不存在的 `src/` 塞 `sys.path`。
- 非 editable 安装下静默读到空配置（看起来像"一层引擎都没启用"）：资源根改为逐级向上验证，找不到直接报错。

### Security

- **命中敏感信息的 PDF 页整页栅格化**（该页文字层消失）：给文字层盖黑块的话原文仍可被复制/搜索，
  那等于没脱敏。未命中的页原样保留矢量文字与体积。由 `test_pdf_output.py` 锁死。
- 引擎起不来时**不产出任何文件**（退出码 1），不会把"少一层检测"的结果报成已处理。
- `mapping.json` 含全部敏感原文，文档各处明确标注"切勿与脱敏件一起外发"。

[Unreleased]: https://github.com/lawyerch-dev/doc-anonymizer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lawyerch-dev/doc-anonymizer/releases/tag/v0.1.0
