# Agent Note: 旧版 Office(.doc/.xls/.wps) 自动转换

Status: implemented

## 问题

旧版二进制 Office（`.doc`/`.xls`/`.wps`）一直记 `unsupported`：`extractors/base.py` 认不出它们，
CLI 记 `unsupported`（退出码 2），Web 直接报不支持。用户只能自己先用 LibreOffice 转成 `.docx`/`.xlsx`
再跑，而且往往连 LibreOffice 都没装。

`docs/cookbook/diagnosing-problems.md` 当初**故意**不做自动转换 —— 怕 LibreOffice 转出的版式被重排，
违背"保留原格式"的承诺，所以坚持人工前置 + 人工核对。

## 决定

在**抽取层**自动转换：`convert.py`（定位 soffice + headless 转换）+ `LegacyOfficeExtractor`
（转换后委托现有 Docx/Table 抽取器；`doc.source_path` 指向转换后的现代文件，回写零改动）。
soffice 走"系统优先 → `var/libreoffice`（下载，`scripts/fetch_libreoffice.sh`）"，不进包。

关键：把语义变化**显式标注**，而不是静默换格式 —— manifest 的 `converted`/`source_suffix`/`output_format`、
CLI 打印"已由 .doc 转换, 版式可能被重排"、Web `trace.converted_from` + 前端提示。缺 soffice 时记
`unsupported` + reason（退出码 2），不是 error。

**推翻了 cookbook 的旧决定**，理由：把"产物格式变了、版式可能重排"写进账本与界面，比让用户手工前置更省事，
也仍然可核对；旧行为可用 `legacy_convert: false` 关掉。

## 代价

- 交付前仍需人工核对版式（转换是近似的）。
- `.wps` 是 WPS 私有格式，soffice 保真度不保证：失败按 `error` 处理。
- 需要 LibreOffice（系统安装或下载到 `var/libreoffice`，300MB–1GB）；缺了不影响其它格式。
