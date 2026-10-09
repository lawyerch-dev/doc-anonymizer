# 产物、账本与退出码

- **命名**：`【脱敏版】<源文件全名>[.<目标扩展名>]`，保留相对子目录（防同名互相覆盖）。
  格式没变就不补扩展名（`a.docx` → `【脱敏版】a.docx`）；变了才补（`a.doc` → `【脱敏版】a.doc.docx`），
  否则 `a.doc` 与 `a.docx` 会撞成同一个名字、**静默丢一个**。命名只由输入决定（不看目录里已有什么），
  否则 `--resume` 与账本记的路径对不上。
  文件名超过文件系统 255 字节上限（APFS/ext4 同值）时**确定性截断**：保住扩展名，
  源名按整字符截短后补 `~+8 位哈希` 防撞名；哈希只由完整目标名算出，同一输入永远同名。
  由 `packages/docanon-core/tests/test_output_layout.py` 锁定，改命名等于改契约。
- **三态**：`manifest.json` 里每个源文件是 `ok` / `error` / `unsupported`。
  **未脱敏不许报成已处理**；新格式/新抽取器必须走这三态并保留非零退出
  （`docanon_core/cli.py` 的 `EXIT_PARTIAL`）。依据是「召回优先（宁多勿漏）」。
  旧格式转换成功的条目额外带 `source_suffix` / `output_format` / `converted: true`（产物的格式变了，要写明）；
  缺 LibreOffice 的旧格式记 `unsupported` 并带 `reason`。
- **退出码**：`0` 全部处理；`1` 输入/配置/引擎有问题（连输出目录都不建）；`2` 有文件没产出结果。
  `2` 是提示不是"跑坏了"（历史 `error`/`unsupported` 记录会让合并后的清单算成 2）。
- **一个 `-o` 就是唯一真相**：`manifest.json`/`mapping.json` 按源文件**累加**（同一 `source` 只更新它那一条）。
  分批跑就往同一个目录跑，不要新建 `out2/`、`out_mp2/` 这类平行目录，也不要预先清空它。
- **账本纪律**（`docanon_core/job.py`）：每处理完一个文件就落盘，先写 `.tmp` 再 `os.replace`。
  改成"整批跑完再写" = 让 Ctrl+C/崩溃丢掉已完成部分的原文与记录。
  `--resume` 判定"已脱敏"必须同时要求**产物文件仍在**；账本读不出来就拒绝执行（退出码 1、一个文件都不碰）。
- `restore` 只吃 UTF-8 文本产物（txt/md/csv）；docx/xlsx/pdf/图片是回写产物，没有可替换的纯文本。
