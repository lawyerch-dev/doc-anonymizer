# 脱敏安全边界

- `mapping.json` 保存**全部敏感原文**（用于还原）：绝不与脱敏产物一起外发或提交。
- **输出目录不能位于输入目录内**：下一次 run 会把上次的 `【脱敏版】*` 当新文档再脱敏一遍。
- **命中敏感信息的 PDF 页必须整页栅格化**（该页文字层消失，不可选中/搜索/再编辑）；
  为什么与代价见 [决策记录](../notes/implemented/architecture/2026-10-06-pdf-hit-pages-rasterized.md)。
  给文字层盖黑块 = 原文仍可复制 = 没脱敏，这条是安全保证不是偷懒；未命中的页原样保留矢量文字与体积。
  由 `test_pdf_output.py` 锁死，README「已知限制」对用户解释同一件事。
- **`restore` 的 remove 空串坑**（事故复盘：[笔记](../notes/implemented/bug-fix/2026-10-06-restore-empty-string.md)）：`remove` 策略的替换值是空串，不是可定位锚点。
  它只进正向表、绝不进 `MappingStore._reverse`；还原走 `restorable_items()`（过滤空键）。
  谁把空串塞回反向表，`str.replace("")` 就会把原文插到每个字符之间——**还原动作反而把敏感信息撒满全篇**。
  回归测试：`packages/docanon-core/tests/test_restore.py`。
- **docx 的抽取与回写必须共用一套遍历**（[笔记](../notes/implemented/bug-fix/2026-10-07-docx-hyperlink-offsets.md)）：
  `paragraph.text` 含超链接里的文字而 `paragraph.runs` 不含，两边各算一套偏移就会**同时**漏掉超链接里的
  敏感值、又把旁边的字改错，而 manifest 报 `ok`。抽取/回写都走 `docx_walk.py`；段落定位失败要抛错，
  不许 `continue` 静默跳过。回归测试：`packages/docanon-core/tests/test_docx_output.py`。
- **任何引擎或端点失败都必须抛错**，不许 `except: return []`。跑前 `prepare_detectors` 对每个引擎调
  `ready()`，起不来就是退出码 1 且不建输出目录。
  把「没答上」写成「零命中」是最坏的失败形态（`docanon_engine_ner_llm/client.py` 的 `LLMError` 是这条边界）。
- **唯一的例外是"还没下模型"那次启动**（`server._preparable`）：打包后的首次使用，模型要在界面上点
  "准备"才下得来，这时 `docanon web` 退出就等于用户永远看不到那个按钮（实测 `.app` 启动即退）。
  所以**只对"有东西可准备"**放行启动；每次脱敏依旧预检（`routes._anonymize`），在那之前点脱敏会被
  明确拦下、不产出少了识别层的产物。配置写错、模型损坏、自备服务连不上都不算可准备，照旧当场退出。
- 非目标：不接云端 API、不依赖 Ollama、不引入 lint/typecheck/CI
  （单人本地工具，测试即门禁，理由见 `docs/architecture.md` §七）。
