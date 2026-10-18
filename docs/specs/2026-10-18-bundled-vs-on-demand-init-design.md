# 初始化形态：按需下载 vs 随包自带（含 LibreOffice 无根便携）— 设计方案

- 日期: 2026-10-18
- 状态: 待评审
- 相关: [总体架构](../architecture.md) · [资源与配置](../../.agent/rules/03-resources.md) ·
  [旧格式转换（前作）](2026-10-08-legacy-office-conversion-design.md) ·
  [旧格式转换决策笔记](../../.agent/notes/implemented/feature/2026-10-08-legacy-office-conversion.md)

## 1. 背景与目标

现状：三样**可选**资产全部靠"按需下载"，但它们各自的处境差得远。

| 资产 | 体积（实测） | 谁负责取 | 现状问题 |
|---|---|---|---|
| file-viewer 预览包 | 232MB → 包内裁到 63MB | `npm run setup` / `dev.sh dist` | 已随包，无问题 |
| ONNX 识别模型（界面默认方案要两个） | **780MB** | `prepare.py`（界面上"准备"） | 可用，但首跑要等 |
| LLM GGUF 权重 | **2.78GB**/个（本机 `var/models` 合计 5.9G） | `downloads.py` | 可用，但只有"最准"档才需要 |
| **LibreOffice（旧格式转换）** | 300MB–1GB | **没有任何入口会替你取** | **本文档主要对象** |

LibreOffice 这一项的实际状态（读代码 + 实测确认）：

1. `scripts/fetch_libreoffice.sh` 本身是**全自动的**（探 OS/arch → 下载 → 解包 → 去隔离），
   而且 macOS 上**已经是"无根便携"**：从 `.dmg` 解出 `LibreOffice.app` 拷进 `var/libreoffice`，
   不走安装器、不要管理员、不污染系统。缺的不是能力，是**没人替你调用它**。
2. **Windows 整条没有**：脚本兜底分支直接 `die`，而项目**要发 Windows 安装包**。
3. **打包后路径失效**：`resources.WRITABLE` 不含 `libreoffice`，所以它按**资源根**解析；
   而打包后资源根在只读的 `.app` 里（还可能被 App Translocation 挂到随机只读路径）。
4. **没有界面入口**：`prepare.needed()` 只返回 ONNX 与大模型两样。

另外，目标群体（律师/法务）**可能处在内网或离线环境**：首跑下载 780MB–3GB，与"手动装
LibreOffice"是同一性质的体验痛点，只是量级不同。

**目标**：两种形态都成立，且共用一套代码。

- **在线（默认，lite）**：现有形态 —— 包小，首次使用按需下载。
- **免安装/离线（full）**：默认 ONNX 与 LibreOffice 随包自带，打开即用；
  资源也可指向"指定的免安装目录"（U 盘 / 内网共享盘）。

**非目标（YAGNI）**：不引入 Docker / 服务端 / 云端转换 API（违反"全离线、不接云端 API"与
[运行期零 node](../../.agent/rules/07-frontend.md)）；不把 GGUF 打进包；不引入第三方 JS 转换器
（见 §7）；不改任何按需下载的现有机制。

## 2. 要修订的旧决定（必须显式改，否则文档与代码漂移）

| 原决定 | 出处 | 本次修订 |
|---|---|---|
| "不做 wheel 自包含" | [architecture.md §七](../architecture.md) | **仍然不做**；新增的是**构建风味** `full`，不是 wheel 自包含 |
| "可选资源按需下载、不进包" | [rules/03-resources.md](../../.agent/rules/03-resources.md) | 追加一句：`full` 风味下，**默认 ONNX 与 LibreOffice** 是例外 |
| "模型不进包（5.9G）" | [dev.sh](../../scripts/dev.sh) 的 `cmd_dist` | **仍然成立**（GGUF 永不进包）；但**默认 ONNX 780MB** 在 `full` 里进 |

`test_docs.py` 抓不到这类语义漂移，所以这三处要**跟着这次改动一起改**。

## 3. 资产分级（决定了 full 包能带什么）

| 资产 | 体积 | lite | full | 理由 |
|---|---|---|---|---|
| 前端 + 侧车 + samples + configs | ~1MB + 侧车 | ✅ | ✅ | 现在的包内内容 |
| file-viewer（裁剪后） | 63MB | ✅ | ✅ | 现状 |
| ONNX `gyr66` + `pii-engineer` | 780MB | ❌ 按需下 | ✅ 随包 | **界面默认方案就要它**，是"离线即可用"的核心价值 |
| LibreOffice（分平台） | 待实测 | ❌ 按需下 | ✅ 随包 | 旧格式支持的唯一质量方案 |
| LLM GGUF | 2.78GB/个 | ❌ 按需下 | ❌ **永不进包** | 只有"最准"档用；进了包就是 3–4GB 安装包换三分之一功能 |

`full` 包的体积量级：63 + 780 + LibreOffice（+ 侧车）。**LibreOffice 的实际体积必须真机实测后再定档**
（见 §5）。

## 4. 核心设计：跨根查找（这是最容易做错的一处）

**铁律不能动**：只读资源按**资源根**解析、下载来的可写状态按**数据根**（`DOCANON_DATA`）解析。
[resources.py](../../packages/docanon-core/src/docanon_core/resources.py) 把这套写得很清楚，理由也硬
（打包后资源根可能在只读的随机挂载点）。

**同时，"布局只有一处真相"也不能破**：`LAYOUT` 里仍然只有一行 `libreoffice: var/libreoffice`。

⚠️ **直觉做法会踩坑**：把 `libreoffice` 加进 `WRITABLE` 看着像"一行修"，但那样会把它指向数据根，
於是 **full 包自带的那份（在资源根里）立刻读不到**。反过来，不改 `WRITABLE` 则下载来的那份读不到。
两边都要，只能**按优先级查多个候选位置**：

```text
DOCANON_SOFFICE（显式覆盖：坏路径也不回退，现状不变）
  → 系统安装（shutil.which；macOS 另加 /Applications/LibreOffice.app/...）
  → 数据根 var/libreoffice    ← 下载来的（在线形态）
  → 资源根 var/libreoffice    ← 随包自带的（full 形态）★ 新增
```

实现约束（两条，都很容易被绕过）：

1. **相对路径仍只从 `LAYOUT` 取**，不许在 `convert.py` 里写死 `"var/libreoffice"` —— 那会把布局
   知识复制成第二份，正是 `LAYOUT` 存在的意义所在。
2. 两个候选是**同一相对路径在两个根上**，所以应该在 `resources` 上暴露"同路径跨根候选项"
   的能力，由 `convert.find_soffice` 迭代；而不是新开一张平行布局表。

配套：**`docanon doctor` 与 `docanon engines` 必须报出"这份资源是从哪个根读到的"** ——
否则就会出现"明明带了 / 明明下了，却读不到"，而本项目的既定姿态是"少一层宁可报错，也不许静默"。

## 5. Windows 专项：本文档**不替它下结论**

`--convert-to` 在 Windows 上确实可用（官方 wiki 与参数文档均确认 `soffice.exe --convert-to` 形式），
但这条路有三个必须先解决的点：

### 5.1 headless 应当优先用 `soffice.com`，不是 `soffice.exe`

官方启动参数文档明确写着：`soffice.exe` 是**无控制台**版本，"不需要控制台时才用它"；
命令行 / headless 场景要用 **`soffice.com`**。这对我们是硬约束 —— 因为
[`to_modern`](../../packages/docanon-core/src/docanon_core/convert.py) 依赖三件事：
`proc.returncode != 0` 判失败、`proc.stderr or proc.stdout` 取失败原因、**同步返回后产物已经落盘**。
GUI 子系统的程序可能**丢掉 stdout/stderr**，甚至**立刻返回而实际还在后台跑** ——
那会把"转换失败"误判成成功或空产物，正是最坏的一类失败。**必须在真 Windows 上实测确认用哪一个。**

### 5.2 Windows 没有 macOS 那种"解包即可跑"的形态

macOS 的 `.app` 是自包含 bundle，所以我们解 `.dmg` 就能跑。Windows 官方发的是 **`.msi`（安装式）**，
而有社区反馈指出：**只把 `program/` 目录拷到另一台机器，很可能跑不起来**（安装过程会往系统侧写
注册等）。所以 Windows 的"无根便携"不是现成的，需要实测这两条：

- `msiexec /a <msi> TARGETDIR=<用户目录> /qn`（管理式安装，解包到指定目录）能否在**不要管理员**的前提下解出可用树；
- 第三方解包（如 7-Zip / msitools）解出的树能否 headless 跑。

**结论：Windows 的自动化方案必须先在一台真 Windows 上验证，本文档只列判定标准，不预先选路。**

### 5.3 现有代码在 Windows 上有四处必坏（已读代码确认）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `find_soffice` 的 `bundled.rglob("soffice")` | Windows 上二进制叫 `soffice.exe` / `soffice.com`，**带扩展名**，`rglob("soffice")` 一个都匹配不到 |
| 2 | `_usable()` 的 `os.access(p, os.X_OK)` | Windows 没有 Unix 式执行位，`X_OK` 退化成"文件是否存在" → 该方法 docstring 承诺的"不可执行就不算可用"**在 Windows 上失效** |
| 3 | 整体 | 无 `soffice.com` 优先级、无 Windows 候选路径（`_MAC_SOFFICE` 是 mac 专属） |
| 4 | `fetch_libreoffice.sh` | Windows 分支直接 `die`，**完全没有实现** |

## 6. 两个风味，而不是改现有机制

**不要动按需下载** —— 那条路已经跑通、被测试锁着，改它是纯风险。改为**一个代码库、两个构建风味**：

| 风味 | 内容 | 首次使用 |
|---|---|---|
| **lite（默认，现状）** | 前端 + 侧车 + 裁剪后的 file-viewer | 按需下载 ONNX / LibreOffice / GGUF |
| **full（免安装 / 离线）** | lite + 默认 ONNX（780MB）+ LibreOffice（分平台） | 打开即用；GGUF 仍按需下 |

"免安装形态"其实**已经是半成品**：`DOCANON_ROOT` 早就能把资源根指到任意目录（U 盘 / 内网盘）。
缺的只是：一个用户可见的"资源目录"入口 + `doctor` 报来源 + 那份 `full` 包。

## 7. 明确不采纳的方案（省得以后再评估一遍）

| 方案 | 为什么不采纳 |
|---|---|
| Docker / HTTP 转换微服务 | 目标用户双击 `.app` 就用，机器上没有 Docker；且**文档经网络送出去转换 = 新增泄漏面**，与"全离线、不接云端 API"冲突 |
| 包管理器静默安装（apt / winget / brew） | 要管理员权限、动用户系统、企业管控环境会被拦；且我们是 macOS/Windows 桌面版，不走 apt |
| Serverless 轻量构建（如函数计算方案） | Linux + 云环境，桌面 App 用不上（且其打包限制本就是为函数运行时定的） |
| 第三方 JS/TS 转换库（如从零实现 OOXML 解析器的那类） | 接入要给桌面版加**Node 运行期**，破"运行期零 node"；且"有损报告"不能替代正确性 —— 报告说干净却静默丢内容，对脱敏工具就是漏脱敏。**若将来放宽该边界，值得重新评估**，但不在本次范围 |

## 8. 防"明明带了/下了却读不到"的查找规则

对每一项可选资源，查找顺序固定为：

```text
显式环境变量（该资源的专用覆盖，如 DOCANON_SOFFICE）
  → 用户指定目录（设置里那一项）
  → 数据根（下载来的）
  → 资源根（随包自带的）
```

两条纪律：

- **读不到就报错、不许静默回落到"猜"的位置**（沿用 `ResourceRootError` 的既有姿态）。
- 每个根都必须能在诊断输出里被点名（"来源"字段），否则这类问题无法排查。

## 9. 测试

- **跨根查找三态**：数据根有 / 资源根有 / 都没有 —— 分别命中、命中并报出来源、报"缺失 + 可操作原因"。
  落点：`packages/docanon-core/tests/test_convert.py`。
- **防回归**：`find_soffice` 不许把 `"var/libreoffice"` 字面量写进 `convert.py`（布局唯一真相）。
- **Windows 分支**：在 mac 上按"平台不适用"跳过（本仓已有此惯例，见
  `packages/docanon-core/tests/test_server.py` 里那条 Windows 用例）。Windows 真机验证另立一项。
- **full 风味的资产清单守卫**：脚本断言 `full` 只带 ONNX + LibreOffice、**不含 GGUF** ——
  防止以后有人手一滑把 2.78GB 塞进去。
- 改测试要同步 `AGENTS.md` 里的「（N 项，约 M 秒）」（`test_docs.py` 会红，故意）。

## 10. 文档同步（一源一址纪律）

- [architecture.md §七](../architecture.md) 那三行、[rules/03-resources.md](../../.agent/rules/03-resources.md)：
  按 §2 修订，并说清 `full` 的例外范围。
- [README.md](../../README.md) / [docs/quickstart.md](../quickstart.md)（含英文孪生）：讲清"两种形态"与
  "旧格式为何要准备一次"。
- [scripts/README.md](../../scripts/README.md)：`fetch_libreoffice.sh` 的目标目录覆盖参数。
- [.agent/notes/](../../.agent/notes/)：留一条决策笔记（含被修订的旧决定与代价）。
- 本文档登记进 `tests/test_docs.py` 的 `RECORDS`（设计文档属记录类）。

## 11. 风险

- **macOS Gatekeeper 与首次 profile 初始化**：解出的 `.app` 要 `xattr -dr`（脚本已有），
  但首次 headless 运行会初始化 profile，期间明显卡顿 —— 用户会以为卡死。转换前必须给
  "正在准备转换能力"的进度提示，不能只转圈。
- **Windows便携性未验证**（§5.2）：这是 `full` 包 Windows 版与 Windows 自动获取的共同前置。
- **`full` 包体积、签名与公证**：installer 从几百 MB 涨到 GB 级，CI 时间与分发成本都要重估。
- **必须懒触发**：只有用户第一次拖入 `.doc/.xls/.wps`（或选了需要模型的方案）才提示准备。
  做成"启动即下载"会比现在的痛点更糟 —— 只用 `.docx`/`.pdf` 的用户要被白等一次 GB 级下载。
- **不要为了省事把两个根合并**：合并＝让"只读/可写"分家失效，打包后必炸（见 §4）。

## 12. 落地顺序

1. **先修 Windows 侧的 4 处必坏点**（§5.3）—— 与本次双模设计独立，是修 bug 不是加功能。
2. **跨根查找**（§4）：`resources` 提供跨根候选 + `find_soffice` 迭代 + `doctor` 报来源。
   **（已落地）**
3. **Windows 真机验证**（§5.1、§5.2）—— 不通过则 `full` 的 Windows 版先不做，别的平台不受影响。
4. **接进 prepare 流程**（懒触发）+ 前端那一项（文案纪律：**不出现 "LibreOffice" 等技术词**，
   见 `apps/web/src/components/OnboardingWizard.tsx` 既有约定）。
5. **`full` 构建风味** + 资产清单守卫；同步 §10 的文档。
