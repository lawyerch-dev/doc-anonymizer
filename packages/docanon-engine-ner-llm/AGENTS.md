# AGENTS.md — docanon-engine-ner-llm

LLM NER 引擎：标准库写的 OpenAI 兼容客户端（`client.py`）+ 检测器（`detector.py`），只连本机 `llama-server`。

- **只依赖 `docanon-contract`**（传输层只用标准库）—— 所以这个包能整块搬走。
- **端点答不上来一律抛 `LLMError`**，绝不返回空：把"没答上"当成"零命中"是最坏的失败形态。
- `LLMConfig` 住在本包；core 的 `config.py` 反过来 import 它。
- 测试：`packages/docanon-engine-ner-llm/tests/test_llm_detector.py`（用假端点，不需要真模型）。

细则 → [`02-packages.md`](../../.agent/rules/02-packages.md)、[`05-security.md`](../../.agent/rules/05-security.md)
