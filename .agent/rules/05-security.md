# 脱敏安全边界

- `mapping.json` 保存**全部敏感原文**（用于还原）：绝不与脱敏产物一起外发或提交。
- **输出目录不能位于输入目录内**：下一次 run 会把上次的 `.redacted.*` 当新文档再脱敏一遍。
- **命中敏感信息的 PDF 页必须整页栅格化**（该页文字层消失，不可选中/搜索/再编辑）；
  为什么与代价见 [决策记录](../notes/implemented/architecture/2026-10-06-pdf-hit-pages-rasterized.md)。
  给文字层盖黑块 = 原文仍可复制 = 没脱敏，这条是安全保证不是偷懒；未命中的页原样保留矢量文字与体积。
  由 `test_pdf_output.py` 锁死，README「已知限制」对用户解释同一件事。
- **`restore` 的 remove 空串坑**（事故复盘：[笔记](../notes/implemented/bug-fix/2026-10-06-restore-empty-string.md)）：`remove` 策略的替换值是空串，不是可定位锚点。
  它只进正向表、绝不进 `MappingStore._reverse`；还原走 `restorable_items()`（过滤空键）。
  谁把空串塞回反向表，`str.replace("")` 就会把原文插到每个字符之间——**还原动作反而把敏感信息撒满全篇**。
  回归测试：`packages/docanon-core/tests/test_restore.py`。
- **任何引擎或端点失败都必须抛错**，不许 `except: return []`。跑前 `prepare_detectors` 对每个引擎调
  `ready()`，起不来就是退出码 1 且不建输出目录（`docanon web` 同样拒绝启动）。
  把「没答上」写成「零命中」是最坏的失败形态（`docanon_engine_ner_llm/client.py` 的 `LLMError` 是这条边界）。
- 非目标：不接云端 API、不依赖 Ollama、不引入 lint/typecheck/CI
  （单人本地工具，测试即门禁，理由见 `docs/architecture.md` §七）。
