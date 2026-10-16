# 工作台布局改造（参考 LawRedact，纯前端）

## Context

参考 lawredact.com 的工作台布局调整现有产品界面。现状（[App.tsx](file:///Users/bluer/Documents/_terminal/doc-anonymizer/apps/web/src/App.tsx)）是「简单顶栏 + 左 280px 堆叠栏（列表/按钮/进度/统计/还原）+ 右双栏预览」，操作分散、统计薄弱、批量复核时看不到全局。

目标结构（**只调结构，沿用黑白灰+红强调配色**，不引入紫/橙）：

```
TopBar(h-11)  Logo/版本 · +文件(菜单) · 一键脱敏 · 下载/还原(按上下文) · 方案▾ · 设置/日志/明暗
EntityFilter  实体类型 chips 横条（点选过滤文件列表+敏感明细；0 命中整条隐藏）
─────────────────────────────────────────────────────────────────────
左 264px 文件列表 │ 中：双栏/原文/脱敏 三模式预览 │ 右 300px 质量面板
                  ProgressBar（跑中时底栏上浮条）
StatusBar(h-7)  本地离线运行 · 当前方案 · 版本
```

**本期不做**（用户确认另立任务）：文档内手动涂抹/补充脱敏、文档内实体高亮（预览是 Flyfish 黑盒 SDK，技术不可行）、字号行距缩放控制、CPU/内存（`/health` 无数据，不改后端）。

## 硬约束（违反即回归）

- E2E 钩子保留：`#loadSamples` `.preset` `#run` `#cancelRun` `.doc-row`(+`data-status`) `#editUploadRule` `#batchSummary` `#stats` `#paneSrc/#paneOut .placeholder` `#downloadZip`；[webkit-check.mjs](file:///Users/bluer/Documents/_terminal/doc-anonymizer/tests/e2e/webkit/webkit-check.mjs) 还依赖：
  - `#pickFolder` 常驻且 textContent 含「上传中 N/M」做进度轮询、其 `closest('div')` 内有提示 `<p>`（folderNotes）→ **该按钮保留在文件列表卡片内**，顶栏「+文件」菜单与它调同一 opener。
  - `.doc-row` 前两个子元素必须是 span，第二个是文件名（`span:nth-of-type(2)`）；「✓ N 处」文案保留。扩展名块占用原 📄 的第一个 span，状态点用 `<i>`，不加额外前置元素。
- 改钩子位置必须同步 [.agent/rules/07-frontend.md](file:///Users/bluer/Documents/_terminal/doc-anonymizer/.agent/rules/07-frontend.md) 第 32-33 行（六条不可违反第 6 条），与代码同提交。
- 纯前端：后端、handler 逻辑（run/runBatch/pickFolder/switchConfig/影子配置）一行不动。

## 新增组件（apps/web/src/components/）

均受控、无数据获取；**所有数据状态与异步 handler 留在 App.tsx**，App 唯一新增状态 `activeType: string | null`。

1. **TopBar.tsx** — 纯展示。props：version/configDirty；方案下拉（configs+configRef+switchConfig，DropdownMenuRadioGroup，选中打勾，影子标「·」）；`#run` 原生按钮（canRun 时渲染，running 禁用文案「脱敏中…」，点击仍走 `folderMode?runBatch:run`）；「+文件」DropdownMenu（上传/选文件夹，仅触发 App 的隐藏 input opener，input 留 App 不进 Portal）；下载组（单文件下载脱敏件 / 批次 `#downloadZip`+映射表链接，title 警告保留）；`<xl` 显示「还原」按钮（开左抽屉）；设置/日志/明暗。设置抽屉内 ConfigPanel 的方案选择保留，两处共用 switchConfig。
2. **EntityFilter.tsx** — `items:{type,label,count}[]`（count>0、按数量降序）+ activeType/onSelect；横排 `overflow-x-auto scroll-thin`；首项「全部」；选中态 selected 色系，未选 border/muted。
3. **CompareView.tsx** — Base UI Tabs **只用 Root/List/Trigger 作分段控件，不用 TabsContent**；两个 Preview 常驻不卸载：split 用 `grid lg:grid-cols-2`；单视图用 `absolute inset-0`+非活动窗格 `invisible pointer-events-none`（**禁止 display:none/改 key**，避免 Flyfish 以 0 尺寸初始化或重挂）。Preview.tsx 逻辑零改动。
4. **QualityPanel.tsx**（取代 StatsCard.tsx，删除该文件）— 大号「已脱敏 N 处」+ 诚实口径（单文件 restorable→「N 处全部可还原」；批次→`ok/total 份成功`，unsupported/error 分别显名，error 用 destructive；不发明评分算法）；Accordion 识别统计两列 grid（圆点+中文名+数量，默认展开 keepMounted）；`#stats`、`#batchSummary` 挂在这里。另导出无 id 的 `QualityHead`/`StatsGrid` 供窄屏兜底复用（保证全页唯一 id；右栏仅 `hidden xl:flex`，id 仍在 DOM）。
5. **DetectionList.tsx** — 仅单文件且有 `trace.detections` 时渲染：折叠「敏感明细（N）」，每行 `原文 → 占位符`（无 replacement 按 keep/remove 口径显示，与 LogModal 一致）+ 类型 Badge；受 activeType 过滤。
6. **RightPanel.tsx** — w-300 纵列：QualityPanel → DetectionList → 现有 RestorePanel（props 原样透传，组件不改）。
7. **ProgressBar.tsx** — 现有 #progress JSX 整体外迁，running 时底栏上浮条（label/文件名/`bg-selected` 进度/已用秒数/8 秒提示/`#cancelRun`）。
8. **StatusBar.tsx** — h-7 边框条：离线点 +「方案：{label}」+ v{version}，无新接口。

## 改动文件

- **App.tsx**：JSX 换为上述组件；隐藏 file/folder input 留 App；activeType 派生：

```ts
const scopeCounts = folderMode
  ? batchRows.filter(r => r.status === "ok")
      .reduce((acc, r) => { for (const [k,v] of Object.entries(r.counts ?? {})) acc[k]=(acc[k]??0)+v; return acc; }, {})
  : (result?.counts ?? {});
// entityItems: entries→filter(>0)→entityLabel→降序；传给面板/Filter 的始终是未过滤的 scopeCounts
const filteredRows = activeType ? visibleRows.filter(r => (r.counts?.[activeType] ?? 0) > 0) : visibleRows;
const filteredDetections = (result?.trace?.detections ?? []).filter(d => !activeType || d.entity_type === activeType);
```

  `setActiveType(null)` 四个重置点：pickFolder、onExitFolder、pickRow、run/runBatch 开头。过滤空态：「这批文件里没有命中「X」的」+「显示全部」。
- **PresetList.tsx**（不改名，避免文档漂移）：删上传/文件夹按钮与两个 input；保留 `#loadSamples`、常驻 `#pickFolder`、文件夹名/返回/skipNote/规则摘要区、三步引导；行渲染：首 span 改为扩展名中性块（`border bg-muted`，不用彩色区分类型），状态点 `<i>`（running 加 animate-pulse，ok=selected，error=destructive）。
- **lib/formats.ts**：追加 `ENTITY_DOT_CLS`（5 档：人相关=bg-selected；强标识号=bg-primary；联系/网络=mut-foreground/70；时间金额密钥=/35；CUSTOM/DEFAULT=空心）+ `entityDotClass()`；类名写死字面量供 Tailwind4 扫描。
- **styles.css**：不加色变量。
- **.agent/rules/07-frontend.md**：钩子位置说明同步（顶栏/右栏/浮条）。
- RestorePanel `id="restore"` 双挂载问题：窄屏兜底外层包 `#restoreWrap.xl\:hidden`，接受 hidden 副本不可交互。

## 响应式

- ≥1280(xl)：三栏（Playwright 默认 1280 宽，断点定死后不再调）；右栏内部 scroll-thin。
- 1024–1279：列表+中栏两栏；质量/还原走抽屉内 `xl:hidden` 兜底卡。
- <1024：沿用现有抽屉机制；中栏双 Preview 上下堆叠；split 断点类不变。

## 实施顺序（每步 build 通过、独立提交）

1. ProgressBar/StatusBar 外迁（纯搬 JSX）
2. TopBar 第一批：Logo/设置/日志/明暗/`#run`/下载组
3. +文件菜单 + input 上移；PresetList 瘦身但保留 `#pickFolder`
4. 方案下拉进顶栏
5. EntityFilter + activeType 过滤联动（含四个重置点、空态）
6. CompareView 三模式（visibility 保活）
7. RightPanel/QualityPanel/DetectionList，删 StatsCard，窄屏兜底，行增强
8. 同步 07-frontend.md；全量验证

## 验证

- 每步：`npx tsc --noEmit`（apps/web）+ `npm run build:web`
- 起后端 `npm run dev:backend`（:8000）后 `node tests/e2e/webkit/webkit-check.mjs` 与 `jitter-check.mjs` 全绿（重点：单文件 #run/#stats、文件夹 #pickFolder 上传轮询/folderNotes/改规则重筛/zip、切 tab 后 viewer 不重载不抖动）
- 手测（:5173）：明暗双色；chips 过滤单文件+批次；批次中途取消；下载/映射表/还原卡（WIP 禁用态不变）；窗口拖到 1100/900/600 宽逐档检查抽屉与兜底；OnboardingWizard/error 条位置
- 不跑全量 npm test、不提交不发版（用户自行验证）
