---
name: add-a-detector
description: Use when adding a new detector (rule/dictionary-style) inside docanon-core, or when a config key for a detector must be wired end to end.
---

# 加一个检测器（core 内）

1. 在 `packages/docanon-core/src/docanon_core/detectors/` 新建模块，实现 `Detector`：
   `name`、`capabilities()`（认识什么）、`ready()`（起不来给原因）、`detect(block)`。
2. 在 `detectors/base.py` 的 `DETECTORS` 注册表登记一行（键名 = 配置键）。
3. 在 `packages/docanon-core/src/docanon_core/config.py` 里给它默认开关与参数（默认关闭）；
   `configs/default.yaml`、`onnx.yaml`、`llm.yaml` 里同步键名。
4. 测试：`packages/docanon-core/tests/test_detectors.py` 加语义用例；`test_pipeline.py` 跑一遍端到端。

**必须遵守**：起不来要报错、不许静默返回空（否则等于漏脱敏）。见 `.agent/rules/02-packages.md`、`05-security.md`。

验证：

```bash
npm run test:py                                    # 全量
.venv/bin/docanon engines -c configs/onnx.yaml     # 新引擎要在清单里显示"可用"或原因
```
