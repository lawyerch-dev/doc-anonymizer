# AGENTS.md — docanon-engine-ner-onnx

ONNX 中文 NER 引擎：**构造即加载**（模型/词表有问题在 `__init__` 就报错，绝不静默返回零命中）。

- 只许依赖 `docanon-contract` + `numpy`/`onnxruntime`/`tokenizers`。
- **词表是 app 传进来的必填参数**（`entity_map`）：空表 = `ValueError`；标签→实体类型映射住在 core 的 `config.py`。
- 模型在 `var/models/onnx/{gyr66,pii-engineer}`（`npm run models` 取，约 830MB）；缺模型时构造报 `FileNotFoundError`。
- 测试：`packages/docanon-engine-ner-onnx/tests/test_onnx_detector.py`（真模型不在就 skip）。

细则 → [`02-packages.md`](../../.agent/rules/02-packages.md)、[`03-resources.md`](../../.agent/rules/03-resources.md)
