# 批量脱敏（选择文件夹）设计

> 状态：已批准，待实施
> 日期：2026-10-12
> 现状以 [README](../../README.md)、[AGENTS.md](../../AGENTS.md)、[architecture](../architecture.md) 为准；本文是当时的完整设计。

## 背景与问题

Web 界面现在**只能一份一份地选**：`/api/upload` 一次收一个文件（base64、每个文件一个 token），
`/api/anonymize` 一次跑一份（`token` 或 `preset`），结果只回一份的 `output_name`/`counts`。

实际使用里，待处理的是一整个文件夹（一个案子的十几份材料）。现在的做法是逐个点、逐个跑、逐个下载，
产物散在一堆 `outputs/<token>/` 里，还得手动拼回目录结构 —— 这正是 CLI 早就解决、而界面没接上的事：

- `pipeline.process_file(path, out_dir, config, store, rel=..., progress=..., cancel=...)` **本来就支持
  `rel`**：`docs/子目录/sample.docx → out/子目录/【脱敏版】sample.docx`（[04-outputs](../../.agent/rules/04-outputs.md)）。
- CLI 的 `docanon run <目录> -o <输出>` 已经是一个"整批 + 账本 + 三态"的完整实现。

所以这次不是造新能力，而是**把已有的批量语义接到界面上**。

## 目标与非目标

**目标**

- 界面上能**选一个文件夹**，把里面所有可脱敏文档（含子目录）一次跑完。
- 产物**保留相对目录结构**，一个批次**一次打包取走**（zip），同时每份可单独预览/单独下载。
- 进度看得见：上传显示「上传 12/41」，跑批显示「第 12/41 份 · <文件名> · 正在识别敏感信息 3/8 段」
  （后半段直接复用 `formats.ts` 现有的阶段文案，不另写一套），可取消。
- 有文件没产出结果时**逐个说清楚**（不支持的类型 / 失败原因），不许报成"全都处理好了"。

**非目标**

- 不做"后端直读本地任意目录"（桌面壳的 native 目录读取）。理由：`docanon web` 绑在 127.0.0.1 且**无鉴权**，
  开一个"按路径读取"的口子等于给本机任何网页一个读取任意文件并取回内容的通道。
  浏览器与桌面壳统一走上传（本机回环，几百 MB 也是秒级）。
- 不做断点续跑（`--resume`）、不做批次历史/重跑、不做自动去重。
- 不改产物命名与账本契约（复用现有 `【脱敏版】` 命名与 `MappingStore` 累加语义）。
- 不做多批次并发（沿用「单进程单人用、一次一个任务」的既有假设）。

## 不变量（硬约束）

1. **少一层必须报错**：批次里每个文件走 `ok` / `unsupported` / `error` 三态，界面必须把后两类显式列出；
   全批一个都没成，界面不能说"完成"。
2. **产物命名与账本纪律不变**：命名只由输入决定；`mapping.json` 按源文件累加；每份处理完即落盘
   （取消或崩溃不丢已完成的部分）。
3. **既有单份流程与 DOM 契约不变**：`#loadSamples` `.preset` `#run` `#paneSrc` `#paneOut` `#stats`
   照旧可用；单份上传/单份跑的行为与现在逐字相同。
4. **路径安全**：任何来自浏览器的相对路径都要过 `_safe_join`（拒 `..`、绝对路径、符号链接逃逸）。
5. **映射表不外发**：zip 里**不含** `mapping.json`（它含原文）；映射表单独一个下载入口并标注风险。

## 架构

### 数据流

```
选文件夹 ──► 前端按 /api/formats + "只收办公文档"筛 ──► 逐份 POST /api/upload(batch=…) ──► uploads/<batch>/<相对路径>
                                             │
                        一次 POST /api/anonymize{batch} ──► 逐份 process_file(rel=相对路径)
                                             │                 产物落 outputs/<out>/<相对目录>/
                                             ▼                 账本落 outputs/<out>/mapping.json
                         200 + results[]（每份三态 + counts + output_url）
                                             ▼
              GET /api/batch/<out>/zip?name=<文件夹名>  ──► 整包下载（不含映射表）
```

### API（新增与扩展）

| 端点 | 变化 | 说明 |
|---|---|---|
| `GET /api/formats` | 新增 | `{"extensions": [".pdf", ".docx", …]}` —— 由抽取器注册表 `extractor_classes()` 的 `extensions` 并集推导（**不许前端硬编码**，也不许在这里另抄一份） |
| `POST /api/upload` | 扩展（向后兼容） | body 增加可选 `batch` 与 `relpath`；带 `batch` 时落 `uploads/<batch>/<relpath>`，返回 `{token: <batch>, filename: <relpath>, url: /uploads/<batch>/<relpath>}`；不带 `batch` 时与现在**逐字相同**（每份一个 token，落 `uploads/<token>/<文件名>`） |
| `POST /api/anonymize` | 扩展 | body 可为 `{batch, config, job}`；与现有 `{preset}` / `{token}` 并列，三者互斥 |
| `GET /api/batch/<out>/zip` | 新增 | 打包 `outputs/<out>/`（**排除 `mapping.json`**），`Content-Disposition` 用 `【脱敏版】<name>.zip`；先落临时文件再发，避免把整包读进内存 |

**`POST /api/anonymize{batch}` 的响应**（200）

```jsonc
{
  "batch": { "cancelled": false },
  "summary": { "total": 41, "ok": 38, "unsupported": 2, "error": 1 },
  "results": [
    { "source": "合同/附件A.docx", "status": "ok",
      "output_name": "【脱敏版】附件A.docx", "output_url": "/outputs/<out>/合同/【脱敏版】附件A.docx",
      "counts": { "PERSON": 3 } },
    { "source": "扫描件/发票.pdf", "status": "unsupported", "reason": "缺 LibreOffice（.doc/.xls 需要）" }
  ],
  "mapping_url": "/outputs/<out>/mapping.json",
  "zip_url": "/api/batch/<out>/zip?name=合同材料"
}
```

- **前端不解析 URL 取 token**：整包地址直接由 `zip_url` 给出（避免"从 output_url 里抠出批次目录"这种脆做法）。
- **取消**：沿用 `progress` 的 cancel Event。取消发生在第 12 份 → **HTTP 200 + `cancelled: true` + 已跑完的部分结果**
  （每份产物是原子落盘的完整产物，不是半成品），界面显示「已取消 · 已跑完 11/41」。
  这与现有单份取消（整份不落产物 → 409）不矛盾：单份是"一个原子单位"，批次是"多个原子单位"。
- **进度**：扩展 `progress.update(job, stage, done, total, file=…, index=…, total_files=…)`，
  `stage/done/total` 语义不变（本份的段数），新增的三个字段只用于批次；前端显示
  「第 12/41 份 · 附件A.docx · 正在识别敏感信息（3/8 段）」。单份流程不传新字段，行为不变。

### 目录与命名

- 上传：`uploads/<batch>/<相对路径>`（保留层级，含子目录）
- 产物：`outputs/<out>/<相对目录>/【脱敏版】<源文件名>`（由 `process_file(rel=…)` 决定，不新写命名逻辑）
- 账本：`outputs/<out>/mapping.json`（`MappingStore` 累加，与 CLI 同语义）
- **跳过与确定性**：遍历时按相对路径排序（同输入同顺序）；**跳过隐藏项**（`.` 开头的文件/目录、
  `__MACOSX`、`Thumbs.db`）—— 否则每个 Mac 文件夹里都会多出一堆 `.DS_Store` 进"不支持"列表。
  隐藏项**不算** unsupported，只在界面上说一句「已忽略 6 个隐藏项」。

### 界面（左栏）

```
┌ 选择文档 ──────────────── 加载示例 ┐
│ [ 选择文件夹… ]  [ 上传文件… ]      │   ← 前者主按钮；后者保留（顺带支持多选）
│ ─ 预过滤提示（选完即出，只给计数）─   │
│  已跳过 3 个非办公文件（.txt 1 · .md 1 · .png 1）· 依赖/构建目录 41 个 · 隐藏项 2 个
│ ─ 列表（每行一个文件）────────────  │
│  📄 合同/附件A.xlsx      ✓ 12 处    │   ← 状态徽标：待跑 / 跑中 / ✓ N 处 / ! 原因 / ✗ 失败
│  📄 扫描件/发票.pdf      ! 缺转换   │   ← 跑不了的办公文档必须进列表（唯一去处，不另开一处重复列）
│ [ 一键脱敏 ]  /  [ 打包下载（zip）] │
│ ┌ 批次汇总 ──────────── 38/41 ┐    │   ← 现有「命中统计」升一级：批次合计 + 三态计数
```

- **收件范围：默认只收办公文档**（`OFFICE_EXTS` = `.doc/.docx/.xls/.xlsx/.wps/.pdf/.csv`）。
  实测反馈：选错一个代码仓库时，里面成百上千个 `.md`/`.txt`/`.png` 也属于"支持的类型"，
  会被当成待脱敏文档全捞进来。要收图片与纯文本（扫描件就是这一档）勾「也收图片与纯文本」，
  勾/取消都按手上的文件清单**立刻重筛**（不用再选一次目录）。跳过的只计数不丢影。
- 点某一行 → 中右两栏显示该份：**已处理好的**给正常的脱敏前后对比（右栏是脱敏件、带下载按钮）；
  **还没处理好的**（待跑 / 跑中 / 未处理 / 失败）右栏显示它的状态与原因，而不是一片空白对比 ——
  `Preview` 的 `placeholder` 天生能承载这段文案，组件不用改。
- 「命中统计」（`#stats`，E2E 契约）在批次下是**各份相加的合计**，仍可折叠、仍靠 `keepMounted` 留在 DOM。
- 新增 DOM 契约钩子：`#pickFolder`、`.doc-row`、`#downloadZip`、`#batchSummary` —— 一并写进
  [rules/07](../../.agent/rules/07-frontend.md)（钩子的唯一出处在那儿）。
- 视觉沿用现有 token：状态徽标只用 `selected` / `destructive` / `muted` 三系，不引入新色；
  沿用 `.scroll-thin` 常驻细滚动条。

### 边界与错误

| 情况 | 行为 |
|---|---|
| 单文件 > 50MB（现状上限） | 该份进"未处理（超过 50MB）"，其余照跑；界面列出 |
| 整批 > 300 份或总字节 > 500MB | **上传前**拒绝并说明（"分两批"），不进入上传 |
| 非办公文档（`.md`/`.txt`/`.png`…） | **默认不收**（实测：选到代码仓库会把成百上千个 `.md` 捞进来）。只计数并写在列表上方"已跳过 N 个非办公文件（.md 12 · .png 3）"；勾「也收图片与纯文本」才收 |
| 依赖/构建目录（`node_modules`/`dist`/`target`…） | 整层跳过，只计数 |
| 旧格式（.doc/.xls）缺 LibreOffice | 后端逐份记 `unsupported` + `reason`（沿用 `convert.unavailable_reason()`），进列表 |
| 同名文件（不同子目录） | 靠相对目录区分，天然不撞 |
| 批次目录不存在/为空 | 400 + 明确原因 |
| 中途取消 | 见上：200 + 部分结果 + `cancelled: true` |
| 全批无可处理文件 | 400 + 原因（"这个文件夹里没有可脱敏的文档"）；前端在此之前就提示"勾上面那个开关" |

## 测试与守卫

- `packages/docanon-core/tests/test_server.py`（或新增 `test_server_batch.py`）：
  批量上传保留子目录、`relpath` 路径穿越被拒、批次跑的三态、取消后已完成部分仍在且账本一致、
  zip 包内容 == 产物集合且**不含 `mapping.json`**、`/api/formats` 与抽取器注册表同源（加一个抽取器就该自动出现）。
- `tests/e2e/webkit/webkit-check.mjs`：加一条文件夹路径（Playwright 的 `setInputFiles` 传多文件时会带上
  `webkitRelativePath`），断言列表出现 `.doc-row`、跑完 `#batchSummary` 的计数正确、零控制台报错。
- 单份流程的既有测试全部保持绿（不变量 3）。

## 风险与结论：`webkitdirectory` 在 WKWebView 里可用

**结论（按钉住的版本查证，2026-10-12）**：可用。壳走 wry **0.57.0**，它的 macOS `WKUIDelegate`
实现了 `webView:runOpenPanelWithParameters:` 并把面板开成"可选目录"：

```rust
// ~/.cargo/registry/src/*/wry-0.57.0/src/wkwebview/class/wry_web_view_ui_delegate.rs:114
open_panel.setCanChooseFiles(true);
open_panel.setAllowsMultipleSelection(open_panel_params.allowsMultipleSelection());
let allow_dir = open_panel_params.allowsDirectories();   // ← 内核对 input 的 webkitdirectory 的反射
open_panel.setCanChooseDirectories(allow_dir);
```

界面仍按"探测不到就不显示入口"写（`"webkitdirectory" in HTMLInputElement.prototype`）：
环境不给就把入口收起来，而不是点了一下什么都不发生。

**唯一未自动化的一步**：在壳里真点一次目录选择（系统原生对话框没法脚本点），见实施计划 Task 11。

兜底（只影响入口这一层，其余设计不变）：壳里加 `tauri-plugin-dialog` 做原生目录选择，
选完仍走同一条上传链路。（`apps/desktop/src-tauri/Cargo.toml` 现在没有任何 tauri 插件。）

## 分期

1. **后端批量**：`/api/formats`、上传带 `batch`/`relpath`、`anonymize{batch}`、进度扩展、zip 端点 + 单测。
2. **界面批量**：文件夹入口、预过滤提示、行状态徽标、批次进度、批次汇总、打包下载 + E2E。
3. **桌面壳入口**：按风险验证结果决定是否需要 `tauri-plugin-dialog`；`rules/07` 与 CHANGELOG 同步。
