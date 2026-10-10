# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，
变更记录格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added

- **首次"初始化"：按方案在后台把该准备的准备好，模型不进安装包**。模型共 5.9G（两个大模型各 2.6G +
  识别模型 779M），塞进安装包没法用；以前取识别模型又只有命令行脚本 —— 用户装完选默认方案，第一次跑
  直接撞上"少一层检测器"。现在：
  - 向导选完方案就自动开始准备（`POST /api/prepare`，轮询进度，可取消 / 重试 / 先跳过），
    **界面上不出现模型、下载、镜像、文件数这些词**，只有一句"正在准备"+进度条。
  - 新增 `configs/onnx_models.yaml`（识别模型目录，数据而非代码；与 `llm_models.yaml` 一样不列入方案下拉）。
  - `server/prepare.py`：**下载前先对候选端点各取 256KB 测速、挑最快的**（国内直连官方 HF 常不可达，
    默认候选含 hf-mirror）；逐文件 `.part` + 原子改名；**文件全齐才报就绪**，少一个宁可报错，
    也不让"少一层识别"的结果蒙混过去；大模型那条转交给现成的下载能力（统一成一份进度）。
  - 准备接口**不做引擎预检**（预检会因为"模型还没下"而报错，那正是这次要解决的事）；跑脱敏时照旧预检。
- **首次使用的欢迎向导**（不是挡路墙，一次即可、右上可关）：只选个方案就能用 —— 每个方案就讲"会抹掉
  哪些数据"（如"只抹号码与联系方式""人名、机构名、地址也一起换掉"），**不出现**模型/下载/ONNX/LLM 这些
  实现词。点选即切换配置并开始。方案列表与设置里 L1 下拉同源；本地记 `docanon.onboarded`，看完不再弹；
  设置抽屉底部的「重新查看欢迎引导」可随时叫回来。选完方案后由后台自动准备（见上一条）。
- **界面上的品牌标、作者与版本号**：顶栏加了内联 SVG 品牌标（盾牌 + 被抹掉的横条：本地不出网、
  敏感信息被抹掉），底部信息条写明「陈恒律师 自用」与版本号，favicon 同款。
  - **版本号只有一处真相**：前端不写死，从 `/health` 读（`docanon_core.__version__` ← `pyproject.toml`），
    有测试锁住两者同源 —— 否则迟早出现"界面写 v0.2.0、包已经是 v0.3.0"。
  - **标与图标都用内联 SVG，不用图片文件也不是在线图床**：本项目运行期全离线，任何外链图片都会让
    界面一开就联网；内联 SVG 零请求，颜色还能直接吃主题 token（`brand` 渐变），明暗两态自动跟随。
- **可分发版：`.app` 脱离仓库也能跑，能直接发给别人**（`npm run dist:desktop`）。此前打的 `.app` 只是
  一层壳 —— Python 后端、配置、前端产物、预览资源全靠"从 `.app` 往上找到仓库根"，拷到别处双击就是
  `ModuleNotFoundError`。现在把 Python 侧车（PyInstaller onedir）与资源根一起收进包：
  - **资源与可写状态分家**（`resources.WRITABLE`）。包内资源根只读（首次运行甚至会被 App Translocation
    挂到只读的随机路径），所以下载得到的模型与用户自建方案改按 `DOCANON_DATA` 解析，桌面壳把它指到
    `~/Library/Application Support/docanon`；源码树里不设这个变量，两个根重合、行为不变。
    `onnx.model_dirs` 随之改走 `resolve_model_dir()`，否则打包后会"模型下好了却加载不到"。
  - **侧车用 onedir 不用 onefile**：onefile 的引导器会先解包再 fork，壳校验的"端口上答话的 pid 是不是
    我拉起的那个子进程"就对不上，会被误判成"端口被旧实例占着"而拒绝启动。
  - 资源根经 Hutch 的 `copy` 进包（`apps/desktop/stage/` 暂存，已被 gitignore）；
    **模型仍不进包**（5.9G），首次使用按方案下载。实测 `.app` 211MB / `.dmg` 214MB（首次启动会在
    `~/Library/Application Support/dev.docanon.app/` 解出约 700MB，那是 Electrobun 自解包的底座）。
  - 壳的启动容错：资源根从"向上找仓库"变成"先认包内的 `docanon/`，再退到仓库"；
    数据目录 `~/Library/Application Support/docanon` 由壳建好并交给后端；侧车的 PATH 里补了
    `/opt/homebrew/bin`（Finder 双击启动时 PATH 很窄，"终端里明明装了 brew 的 llama-server，双击却说没有"）。
  - 顺带：`/health` 之后壳会在日志里打出资源根与数据目录，排查"双击打不开"时先看这一行；
    找不到资源根、后端起不来一律**报错退出**，不留一个空窗口。
  - **官方包改由 Actions 出**（`.github/workflows/build-desktop.yml`）：macOS 与 Windows 两个 runner
    并行、同一条 `scripts/dev.sh dist`（打包步骤只有一份实现，CI 不复制它），打 `v*` tag 时传到
    Release，手动触发时留成 artifact 试跑。**必须在各自系统上打** —— Hutch 是分平台的原生二进制
    （Windows 版就是两个 `.exe`），PyInstaller 也不做交叉编译。**只发 Apple Silicon**（Hutch 没有
    `macos-x64` 产物），**不签名不公证**（macOS 首次右键→「打开」，Windows 首次「仍要运行」）。
- **Windows 版**：Electrobun 在 Windows 上产出的是 `win-x64-doc-anonymizer-Setup.zip`（**zip 里才是
  `Setup.exe`**，per-user 安装、不要管理员）。
  为它改掉了五处 mac-only 的地方：数据目录按平台落（`%LOCALAPPDATA%\docanon`）、侧车路径补 `.exe`、
  PATH 补丁只对 macOS 生效且用 `path.delimiter`、`win.icon` 另出一份 `icon.png`（Hutch 自己转 ICO）、
  以及 **`DOCANON_EXIT_WITH_PARENT` 换机制** —— macOS 靠 `getppid()` 变号（父死被 reparent）判断
  壳没了，Windows 没有 reparent，改成用 `OpenProcess` 探父进程存活；两条路各有一条测试锁着
  （跨平台互斥的那两条按"平台不适用"跳过，反假绿门禁认得这个词，不算假绿）。
  - 第一次 CI 就红在图标上：**`icon.png` 必须是 256×256**（ICO 的最大边长），给 1024 时 Hutch
    直接 `invalid Windows PNG icon: PngTooLarge` 并让整个 Windows 构建失败。现在脚本只出 256，
    `--check` 与 `dev.sh dist` 都会校验（读 PNG 头，跨平台）—— 免得又出现"本地好好的、CI 上红在另一个平台"。
  - 第二次 CI 反过来红在 macOS：`hdiutil: create failed - Resource busy`（造 dmg 的最后一步，
    偶发、与代码无关）。`dev.sh dist` 给这一步留了最多 3 次重试。
  - Release 的资产筛选改成排除法：Windows 的可分发产物是 **zip 不是 exe**，写 `*.exe` 白名单
    会一个都匹配不到（真漏过一次）；排除 Electrobun 更新器用的 `*.tar.zst` 与 `*-update.json` 即可。
  - **一个只在 Windows 上才犯的致命 bug**：那边的 stdio 编码跟着控制台代码页走（cp1252/GBK），
    而 docanon 的输出全是中文 —— 第一句 `print("待处理 11 个文件 …")` 就 `UnicodeEncodeError`
    把进程带走，**Windows 版其实根本跑不起来**。现在 `cli.main()` 一进来就把 stdout/stderr
    掰成 utf-8（`errors="replace"` 兜底），`llama-server` 的日志读取也显式指定了编码
    （`text=True` 会按 locale 解码）。macOS/Linux 默认 utf-8，本地永远看不见这个坑 ——
    它是被下面那步冒烟测试抓出来的。
  - 新增 CI 冒烟：打包后用**真正进包的那份侧车**把 11 个样例跑一遍（含 png 与扫描 pdf，会拉动
    OCR 整条链）。构建绿只说明"打得出来"，不说明"用户装上能跑"。
- **App 图标**：`apps/desktop/icon.svg`（品牌标 + macOS 圆角底，几何按系统图标网格、配色取主题 brand
  三档）→ `scripts/make_app_icon.sh` → `icon.iconset/` + `icon.png` → Hutch 转成包内 `AppIcon.icns`
  与 Windows 的 ICO。此前 Dock 里是默认白图标（构建日志一直在报 `icon source not found`）。标签页
  favicon 也一并从写死的 indigo 换成同一组 brand 色，免得界面里的标、Dock 图标、标签页图标是三个蓝。

### Changed

- **`docanon web` 在"还没有模型"时不再拒绝启动**（`server._preparable`）。原来引擎预检不过就退出，
  这在装完首次使用时会变成死锁：模型正是要在界面上点"准备"才下下来的，退出了用户连那个按钮都看不到
  （实测打包后的 `.app` 启动即 `Web 未启动: 找不到 ONNX 模型` 然后退出）。现在**只对"有东西可准备"**
  放行启动，并且每次脱敏仍然预检，在那之前点脱敏会被明确拦下；配置写错、模型损坏、自备服务连不上
  都不算可准备，照旧当场退出（`.agent/rules/05-security.md`）。
- **界面只留三套方案，默认改成「通用」**：`法律文书交付`（legal.yaml）从设置下拉里也去掉了（向导上一版已经去掉），
  界面只在 **通用 / 最准 / 最快** 三套里选，默认停「通用」（号码、人名、机构、地址都能认，本机小模型、毫秒级）。
  文件**没删** —— 它仍是 CLI 的默认 `-c`、仍有自己的测试与文档，只是产品界面不再暴露
  （`formats.ts` 的 `HIDDEN_SCHEMES`，要恢复删一行即可）。同时把 `DEFAULT_SCHEME` 与 `SCHEME_ORDER`
  同步过去，避免"下拉里没有这个值"的坏状态；README 中英同步。
- **脱敏设置面板重排为「简约大气」**：原先又挤又碎、不仔细看不知道当前配的是啥。现在
  - 抽屉从 32rem 放宽到 42rem，标题区与内容区留白加大（`px-6 py-6`）；
  - **方案下拉提为主控件**（`h-10`、`text-sm font-medium`），"不确定选哪个"的长段解释改成悬停提示；
  - 折叠标题从 13px 提到 `text-base font-semibold`、加大内边距并去掉廉价的下划线悬停；
  - 长段说明（各区块的"为什么/怎么算"）一律下沉为悬停提示（原生 `title`，不引新组件），
    面上只留标题与控件；「检测引擎」的模型单选项也改成整卡可点、选中态与方案一致（描边 + 浅底 + 外环）。
  - 文案来源没变（仍取后端 yaml 的 `hint` 与 `formats.ts` 的表），只改展示方式。

## [0.2.0] — 2026-10-09

面向"真实合同能直接用"的一版：默认方案改成**法律文书交付**档（规矩是"少抹能看出来，多抹看不出来"），
产物命名改成 `【脱敏版】` 前缀并按文件系统上限确定性截断，跑的时候能看见阶段/进度/秒数也能取消，
本地大模型从"自己起服务填地址"变成"界面里选一个就用"，另外修了一个会让**银行卡号整类漏抹**的隐私缺陷。

### Added

- **跑的时候能看见进度、能取消**：最准档跑一份 5000 字的合同要 30-40 秒，界面上原先只有一句"脱敏中…" ——
  既不知道是在转格式、在识别、还是卡死了，也没法中止。现在前端带一个 `job` id 轮询 `/api/progress/{job}`，
  显示"正在准备引擎 / 正在读取原文件 / 正在识别敏感信息 12/101 段（带进度条）/ 正在写回产物"，
  外加**已用秒数**与「取消」按钮（`POST /api/anonymize/cancel`）；**超过 8 秒**才补一句"通常 30-60 秒，
  不想等可以取消"，免得快档也说废话。**取消只在写产物之前生效，且不产出任何文件** —— 半截产物比没产物更危险。
- **Web 会自己把本地大模型服务起好**：`configs/llm.yaml` 现在带 `llm.model_id`（默认推荐那个模型）。
  跑之前后端按需**启动 / 复用 / 切换** `llama-server`（`server/llm_server.py`：只绑 `127.0.0.1`，
  端口从 `8090` 起找空闲的，`DOCANON_LLM_PORT` 可改），并把 `llm.base_url`/`llm.model` 指向它 ——
  用户不用开终端，也不用填地址与别名。起不来（没装 `llama.cpp` / 模型没下 / 启动即退出）一律
  **400 + 原因**，不静默少一层；Web 退出时把子进程一并收掉。**CLI 不变**：一次性进程不在背后留常驻服务，
  仍用 `./scripts/serve_llm.sh`；留空 `llm.model_id` 走"自备服务"那条路，也没变。

### Changed

- **产物命名改成 `【脱敏版】<源文件全名>`**：原先叫 `x.docx.redacted.docx` —— 一串英文后缀堆在文件名中间，
  用户在"下载"里看不出哪个是脱敏版、哪个是原件。现在格式没变就是 `【脱敏版】x.docx`；**格式变了才补目标扩展名**
  （`x.doc` → `【脱敏版】x.doc.docx`），否则同目录里 `x.doc` 与 `x.docx` 会撞成同一个名字、静默丢一个。
  命名仍然只由输入决定（`--resume` 与账本对得上），子目录照旧保留。契约见 `.agent/rules/04-outputs.md`。
- **产物名超过文件系统 255 字节上限时确定性截断**：源名本身能写盘（≤255 字节），加【脱敏版】前缀后就超限
  （真实合同标题动辄 250 字节上下）。超限时保住扩展名，源名按整字符截短后补 `~+8 位短哈希` 防撞名
  —— 哈希只由完整目标名算出，**同一输入永远得到同一个产物名**，`--resume` 与账本依旧对得上；
  不同源文件截短后哈希不同，不会静默互覆。
- **设置里的「检测引擎」从"四个勾选框"改成"一道选择题"**：原先平铺了四项（号码与代码 / 我的敏感词 /
  中文人名与机构 / 本地大模型），把两条轴混在了一起 —— 前三项听起来是"认什么"（实体类别），实际它们是
  "靠什么认"（四个检测器），而且后两项认的东西高度重叠。现在这一层只问一件事：**要不要用模型来认
  人名/机构/地址**（不用模型 / 本机小模型 / 本地大模型；"两个都用"只在当前配置本来就是这样时才出现）。
  `rule` 与 `dictionary` 改为**常开、不给开关**：关掉它们只会静默漏检，而"不想动某一类"本来就有正确的
  表达方式 —— 在 L2 把那一类的策略设成「保持原样」（词表清空 = 词典等于没开）。顺带删掉一个
  **看起来像配置、其实不生效**的模型单选（它只改组件本地状态），服务地址、`--alias` 与启动命令也不再出现。
- **默认方案从「最准（本地大模型）」改成「法律文书交付」**：实测一份真实合同，默认停在「最准」时用户点一下
  就把《民法典》和合同金额一起抹掉，拿到的是废件。规矩改成"**少抹能看出来，多抹看不出来**" —— 默认只抹
  号码与联系方式；要连人名机构一起换（讲课、写案例）下拉里下一项就是，引导行也重写了。`configs/llm.yaml`
  的说明里也补上它的副作用（机构名和金额会一起抹掉）。
- **「运行日志」弹窗改成跟界面同一套设计语言**：原先是一块写死深灰的"开发者控制台"（`slate-900` 系列，
  刻意不跟主题走），在浅色界面里像另一个 app。现在骨架改用共享组件库新增的 `Dialog` 基础件（与设置抽屉的
  `Sheet` 同源、同一套 token 与动效），背景/前景/分隔线/代码块全部走 `popover`/`muted`/`border`；
  **明暗两态都跟着走**，不再有写死的 `slate-*`。内容同时理顺：顶部一条元信息（源文件/抽取器/口径/检测器）
  收进一块浅底卡片，`类型` 列用中文名（与「命中统计」同一套标签，鼠标悬停仍可看原始代码），
  表格字号与「命中统计」对齐。焦点陷阱与 Esc 交给组件库，**关闭后的焦点回收显式指向「运行日志」按钮**
  （`finalFocus`；不指望"上次聚焦的元素"，否则键盘用户会被扔到页面开头），app 里那份手搓的弹窗骨架删掉了。
- 顺带：`packages/ui` 的基础件从 9 个变成 10 个（新增 `primitives/dialog`）。

### Removed

- **配置里的死键 `ocr`**：`configs/*.yaml` 一直写着 `ocr: {enabled: true}`，但 `Config` 没有这个字段、
  `config_from_dict` 也不读它 —— 配了等于没配，还让人以为 OCR 是个开关。删掉，并加一条守卫测试（内置配置的
  顶层键必须是 `Config` 真会读的那些），防止以后再冒出没人读的键。OCR 本身照旧：扫描件/图片自动走，只是它
  从来不是一个可配项。

### Fixed

- **银行卡号只要写成 4 位一组就会整类漏抹**（"6222 0212 3456 7890 123" / "6222-0212-3456-7890"）：
  原先正则只认连续 `\d{16,19}`，而真实合同、回单、委托书里的卡号基本都是分组写法 —— 配了
  `BANK_CARD: mask` 却一个都没抹，且**四个内置档全漏**（等于隐私直接留在交付件里）。
  现在认两种形态：连续 16-19 位、或 4 位一组共 4 组（可带空格/连字符、尾组 1-3 位）。
  分组形态要求"4 位一组"是为了不吃普通数字串（`2026 03 01 2026 03 01` 这类日期串不会被当卡号）。
  用一份 39KB 的虚构复杂合同四档复测：卡号检出从 0 变为 2/2（带空格与纯数字各一）。
- **ONNX 默认不再把"角色"当实体**（`DEFAULT_ONNX_ENTITY_MAP` 去掉 `position` 映射）：实测一份真合同，
  「通用（本机小模型）」档把"课题负责人：王茹月"打成"**：**"、"授权代表（签章）"左边抹、右边留 ——
  半截话比不抹更像"没脱干净"，而角色泛称（审判员/课题组组长/法定代表人/领导）本来就不是身份。
  要角色消失的人，自己写 `onnx.entity_map` 加回去（`POSITION` 的中文名与 L2 策略都还在）。
- **模型层加两道确定性护栏**（实测一份真实合同踩出来的两类误伤，抹掉它们比漏抹危险）：
  - `《》` 里的法规/文件/作品名不当实体 —— 原先《中华人民共和国民法典》被当机构抹成 `《**》`，法律依据就没了；
  - `AMOUNT` 必须带"钱的痕迹"（数字 / `¥` / 元/万/亿）—— 原先期限"十日"被当金额抹掉，合同期限就没了。
  两条都只对 `llm` / `onnx` 生效：`rule` / `dictionary` 是精确匹配（用户明确列的词、写死的号码格式），不受影响。
  **没走提示词**：试过给 4B 模型加"不要标注…"清单，同一份合同上召回反而从 11/11 掉到 9/11 —— 提示词会漂，代码不会。
- **可用性/无障碍收尾（走查发现的硬伤，视觉不变）**：
  - 文档列表每一项从 `div role="button"` 改成**真 `<button>`**（自带键盘 Enter/Space、焦点环与"能按"语义），
    并补 `aria-pressed` 标出当前选中项。
  - 「运行日志」弹窗补 `role="dialog"` + `aria-modal`、**Esc 关闭**、打开时把焦点移进去、关掉后**还回原处**
    （原先键盘用户进去就出不来）。滚动区加 `overscroll-contain`。
  - 错误条加 `role="alert"`：出错时屏幕阅读器会念出来（原先"点了没反应"对看不见的人是零信息）。
  - 窄屏抽屉补**遮罩**（点空白即关）：原先抽屉盖住半屏又没有出口，只能靠"选一个文档"隐式消失。
    顺带删掉一个永远显示不出来的分支（"展开面板"—— 抽屉关着时整个 `aside` 都是 `hidden`）。
  - 预览标题栏的文件名补 `min-w-0`：没有它 flex 项不收缩，超长文件名会把「下载原件」挤出可视区；
    下载链接补 `focus-visible` 环。
  - 修掉一个**拉宽窗口才暴露**的残留：窄屏打开抽屉后把窗口拉宽到 `md` 以上，`fixed`/宽度/阴影没有被
    `md:` 收回，会留一个盖住半屏、又（因为按钮 `md:hidden`）没有出口的固定层。
  - 设置里改了东西没保存就刷新/关页时，用 `beforeunload` 让浏览器确认一次（原先静默丢改动）。

### Added

- **大模型可在界面里选并下载**：L3「本地大模型」原先要填服务地址与模型名 —— 对非技术用户不可理解，
  模型本身还得在终端跑 `./scripts/download_model.sh`。现在：
  - 新资源 `configs/llm_models.yaml`（**数据而非代码**，自己加模型改这个文件）：每条给名字、一句话
    "什么时候用"、仓库与文件名、大小；界面拿它列选项。
  - 没下载的点「下载」即可（后台任务、进度条、可取消、**断了能续**：`.part` + `Range` 续传，
    下完 `os.replace` 原子改名，界面永远看不到半截 `.gguf`）；已下载的显示启动命令。
  - 新接口：`GET /api/models` 增 `llm_models`；`POST /api/models/download`（起 / 查 / 取消）。
    **只收目录里的 `id`，不收 URL** —— 地址一律由目录的 `repo`+`file` 拼出，否则就是个任意下载口。
  - 收录纪律（写进设计与测试）：**只收核实过的地址**，且不把没实测过的数字安到别的模型头上。
    本次只收 [benchmarks](docs/benchmarks.md) 里两个实测 12/12 的 4B；`MiniCPM5-1B`（实测数据对不上）、
    `Anonymizer-1.7B`/`Qwen3.5-9B`（查不到仓库或已弃用）一律不收。设计与决策：
    [设计](docs/specs/2026-10-09-llm-model-download-design.md) ·
    [笔记](.agent/notes/implemented/feature/2026-10-09-llm-model-download.md)。
- **首次联网**：这是本项目第一次让应用主动联网 —— README 徽章从 `offline by design` 改为
  `offline by default`，正文、SECURITY.md 与官网文案都写明"唯一例外是你主动点下载模型"。

### Changed

- **「脱敏口径」改名「脱敏方案」，四套预设各自说清"什么时候用"**：`口径` 是内部行话，用户看不懂。L1 下拉
  原先直接把配置文件的**首行注释**当选项文本，一屏全是字（`法律文书交付件: **只抹"数字型标识 + 联系方式"**,
  其余一律不动。`），还得靠「（当前）」猜。现在：
  - 选项只放**短名**：通用（本机小模型）/ 法律文书交付 / 最快（只用规则）/ 最准（本地大模型），
    「最准（本地大模型）」排最前并默认选中（`formats.ts` 的 `SCHEME_ORDER` / `DEFAULT_SCHEME`，只排序不筛选）；
  - 选中的那套在下面用一句话说**什么时候用它**，另加一行引导："不确定选哪个：默认「最准（本地大模型）」；
    要交出去的材料选「法律文书交付」。"；
  - 这两句就是各自 yaml 开头的**前两行注释** —— 后端 `profiles.describe` 取前两条注释当 `label` + `hint`
    （顺带修掉旧 `label_of` 只取一行、且会被空 `#` 行截断的问题）。所以改文案改 yaml 注释，界面自动跟着变；
    再往下的注释是给改配置的人看的，不会端到用户面前。`GET /api/configs` 新增 `hint` 字段（有测试锁着）。
- **ONNX 模型选择不再露路径**：原先每个模型就是一行 `var/models/onnx/gyr66` 这样的路径，用户无从判断该选
  哪个。改为友好名（通用中文识别 / 个人信息识别）+ 一句话"它认什么"+「推荐」标记，路径只留在悬停提示里；
  并说明推荐怎么选（两个都选实测覆盖率最高，重叠的会自动去掉），一个都不选时立刻警示这一层起不来。
  备注按**目录名**索引（目录可改名/新增，路径是机器上的位置不是身份），认不出的目录回退显示目录名并注明
  "自备模型，没有备注" —— 与"类型代码认不出就照原样显示"同一原则。
- **设置里的「检测引擎」改用用户能懂的说法**：`rule` / `dictionary` / `onnx_ner` / `llm_ner` 是代码里的
  标识，用户要判断的是"这一层能认出我文档里的什么"，所以改名为**号码与代码 / 我的敏感词 / 中文人名与机构 /
  本地大模型**，每个下面一句话说明它靠什么认、有什么代价（要不要联网、快慢、要不要先起服务），并拉开行距。
  另外三处相关问题一并改掉：
  - **按需显示**：勾了「中文人名与机构」才出现模型选择，勾了「本地大模型」才问地址与模型名 ——
    否则一屏技术字段，看着像"全都已经在用"；没勾时不再显示。
  - **模型选择从原生 `<select multiple>` 换成复选框列表**：原控件在浅色界面里会弹出系统深色高亮条，
    且 2 个选项也开 3 行高度。
  - **策略下拉也改中文**（盖成 `**` / 部分打码 / 换成占位符 / 换成假名 / 直接删除 / 保持原样），
    提交的仍是 `redact`/`mask`… 代码；每个下拉补了 `aria-label`（原先仅靠表头，控件本身无可访问名）。
  同时补 `color-scheme: light|dark`（`apps/web/src/styles.css`）—— 原生控件的内部样式（复选框对勾、
  下拉弹出列表、滚动条）不认 CSS 变量，只认它；少了这句暗色下会冒出浅色滚动条与系统深色高亮。
  「自定义敏感词」补了示例 placeholder。后端与配置 schema 未动。
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

[Unreleased]: https://github.com/lawyerch-dev/doc-anonymizer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lawyerch-dev/doc-anonymizer/releases/tag/v0.2.0
[0.1.0]: https://github.com/lawyerch-dev/doc-anonymizer/releases/tag/v0.1.0
