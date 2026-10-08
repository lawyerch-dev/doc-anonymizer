# 旧版 Office 自动转换（.doc/.xls/.wps）— 设计方案

- 日期: 2026-10-08
- 状态: 待评审
- 相关: [2026-10-05 总体设计](2026-10-05-doc-anonymizer-design.md)

## 1. 背景与目标

现状：`.doc` / `.xls` / `.wps`（旧版二进制 Office）**不被支持**。`extractors/base.py` 认不出，
CLI 把它们记成 `unsupported`（退出码 2），Web 端直接报 `不支持的文件类型: .doc`。
用户只能自己用 LibreOffice 手工转成 `.docx`/`.xlsx` 再跑（`docs/cookbook/diagnosing-problems.md`）。

目标：**自动**把旧格式转成现代格式后照常脱敏，且用户不必另行安装 LibreOffice。

成功判据：拖入一个 `.doc`，无人工前置步骤即可得到脱敏产物；账本与界面明确告知"产物格式变了"。

## 2. 被推翻的旧决定与理由

旧约定（`docs/cookbook/diagnosing-problems.md` 第 14 行）**故意不自动转换**：
LibreOffice 转出的 `.docx` 版式会被重排，违背"保留原格式"的承诺，所以要人工核对。

本次**有意推翻**它，前提是把这种语义变化**显式标注**出来（而非静默发生）：

- 产物扩展名从 `.doc` 变成 `.docx` —— 在账本、CLI 输出、Web 结果里都写明"已由 .doc 转换，版式可能被重排"。
- 该行为可关闭（见 §7），关闭后回到旧行为。

## 3. 方案：转换放在抽取层

候选：

| 方案 | 做法 | 取舍 |
|---|---|---|
| **A（采用）** | core 新增 `convert.py` + `LegacyOfficeExtractor`，在抽取时转换 | 复用现有 docx/table 抽取与回写，产物语义自然；改动集中在抽取层 |
| B | 在 `pipeline.process_file` 前做前置转换 | 转换与抽取脱节，抽取器仍认不出 .doc；测试面更碎 |
| C | 各入口（CLI / Web / 桌面）各转一次 | 三处重复，必然漂移 |

选 A。关键前提已核实：回写是**重开 `doc.source_path`**（`redaction/writers.py` 的 `_docx` / `_table`），
所以只要抽取向导把 `source_path` 指向"转换后的现代文件"，回写就自动走原格式分支。

### 数据流

```
process_file(原件.doc)                      # 签名不变
  └─ build_extractor → LegacyOfficeExtractor   # supports(.doc/.xls/.wps)
       ├─ convert.to_modern(原件.doc) → 临时/原件.docx   # soffice 子进程
       ├─ 委托 DocxExtractor/TableExtractor 抽取临时文件
       └─ ExtractedDoc(source_path=临时.docx, meta["format"]="docx",
                       meta["converted_from"]=".doc")
  └─ 检测 / 策略（不变）
  └─ write_output → 原件.doc.redacted.docx     # _out_ext 读 meta["format"] → .docx
  └─ finally: 清理临时目录
```

产物命名沿用现有规则：`_output_path` 拼 `f"{原文件名}.redacted{ext}"`，故为 `合同.doc.redacted.docx`。

**产物扩展名**：`_out_ext`（`pipeline.py`）现对 `format=="table"` 会回落成**源文件**后缀，
对 `.xls` 会错给出 `.xls`（内容是 xlsx）。因此约定：抽取器可在 `ExtractedDoc.meta["out_ext"]`
显式给出产物后缀，`_out_ext` **优先读它**。`LegacyOfficeExtractor` 转换后写死
`meta["out_ext"]`（`.docx` / `.xlsx`），其余抽取器不受影响。

### 扩展名映射

| 源 | soffice 滤镜目标 | 委托给 | 产物 |
|---|---|---|---|
| `.doc` / `.wps` | `docx` | `DocxExtractor` | `.docx` |
| `.xls` | `xlsx` | `TableExtractor` | `.xlsx` |

（`.ppt` 不在本次范围；`.wps` 表格版式由 soffice 尽力转换。）

## 4. LibreOffice（soffice）从哪来

"系统优先 + 按需下载"，遵循仓库既有契约（大体积可选资产不进包，下载到 `var/`，
见 `resources.py` 部署契约与 `scripts/download_model.sh`、`scripts/fetch_file_viewer.sh`）。

新 `resources.LAYOUT` 项：`"libreoffice": "var/libreoffice"`。

`convert.find_soffice()` 解析顺序：

1. 环境变量 `DOCANON_SOFFICE`（显式覆盖）
2. 系统安装：`shutil.which("soffice")`；macOS 追加 `/Applications/LibreOffice.app/Contents/MacOS/soffice`
3. `var/libreoffice/**/soffice`（下载得到）

找不到 → 返回明确原因（供 doctor / 报错使用），**不猜、不静默**。

## 5. 账本与界面标注

- manifest 每条 entry 增加：`source_suffix`、`output_format`、`converted: true|false`。
- CLI：处理该文件时打印 `已由 .doc 转换，版式可能被重排`。
- Web `_anonymize` 响应 `trace` 增加 `converted_from`；前端结果区显示同样提示。
- `SUPPORTED`（`cli.py`）纳入 `.doc/.xls/.wps`，使其走 `run_file` 而非 `unsupported` 兜底桶。

## 6. 失败语义（向后兼容）

| 情况 | 行为 |
|---|---|
| 有 soffice | 转换 → 脱敏，产物 `.docx/.xlsx`，退出码 0 |
| **无 soffice** | 该文件记 `unsupported`，附 `reason: "缺 LibreOffice"`，退出码 2；不炸整轮、不静默 |
| 转换失败 / 超时 / 源损坏 | 该文件记 `error`，错误原文入库；退出码 2 |

与"少一层必须报错"一致：只要没产出脱敏结果，就**必须**被标成未处理，绝不报成"已处理"。
`npm run doctor` 与 `docanon engines` 提前报告 soffice 来源与可用性。

## 7. 配置

新增 `legacy_convert`（默认 `true`）。设为 `false` 时，旧格式一律回落到 `unsupported`（旧行为）。
改 `config.py` 与 `configs/default.yaml`。

## 8. 下载脚本与自检

`scripts/fetch_libreoffice.sh`：探测 OS/arch → 下载 → 解进 `var/libreoffice/`。

- **默认国内镜像**（腾讯云 `mirrors.cloud.tencent.com/libreoffice/libreoffice`，可用
  `DOCANON_LIBREOFFICE_MIRROR` 换成官方或别的镜像）；默认版本取当前 stable（`25.8.7`）。
- Linux：官方 `..._deb.tar.gz` 里只有 `DEBS/*.deb`，用 `dpkg-deb -x` 逐个解开再拷 `opt/` 树。
- macOS：官方 `.dmg`，`hdiutil attach` 后拷 `LibreOffice.app` 进 `var/libreoffice/`，
  再 `xattr -dr com.apple.quarantine` 去掉隔离标记。
- Windows：**不在范围**（脚本明确报错，改用系统安装 + `DOCANON_SOFFICE`）。

`doctor` 增加一行：`libreoffice  系统 | /Applications | var/ | 缺失（运行 scripts/fetch_libreoffice.sh）`。

## 9. 测试

- 单测（`packages/docanon-core/tests/`）：
  - 有 soffice（用 stub / 真机 skip 两态）：`.doc` 产物为 `.docx`、`.xls` 产物为 `.xlsx`（非 `.xls`）、manifest 带 `converted` 标注；
  - 无 soffice：`.doc` 仍记 `unsupported` 且带 reason；
  - 转换失败：记 `error`。
- 改 `packages/docanon-core/tests/test_output_layout.py`（现断言 `.doc → unsupported`，需按新语义更新）。
- 布局测试：`tests/test_layout.py` 认新 `LAYOUT` 项。

## 10. 文档同步（一源一址纪律）

- `README.md` / `README.en.md`、`docs/quickstart.md`：输入支持列表与"已知限制"。
- `docs/cookbook/diagnosing-problems.md` 第 14 行：从"手工转"改为"自动转 + 如何关闭 / 无 soffice 怎么办"。
- `.agent/rules/`：`02-packages.md`（新模块与引擎面）、`03-resources.md`（新资源项）、`04-outputs.md`（账本字段）。
- 根 `AGENTS.md`：如测试数量变化需同步"N 项"。
- `CHANGELOG.md`、`.agent/notes/implemented/`：留一条决策笔记（含被推翻的旧决定）。
- 设计文档登记进 `tests/test_docs.py` 的 `RECORDS`。

## 11. 风险

- **macOS 下载态 LibreOffice 的 Gatekeeper 隔离**：需 `xattr -dr`，且首次 headless 运行可能触发 profile 初始化。
- **下载体积**：每平台 300MB–1GB；首次获取慢，需在 doctor/脚本里给进度与失败可重试。
- **版式重排**：已通过显式标注缓解，但仍是交付时的语义变化，需人工核对（写进文档）。
- **`.wps` 兼容性**：soffice 对 WPS 私有格式的保真度不保证，失败按 `error` 处理。
