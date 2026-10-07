---
name: add-an-engine-package
description: Use when adding a whole new engine as its own package (a new OCR/NER backend), or when an existing engine must be checked for portability.
---

# 加一个引擎包（新的 `packages/docanon-engine-*`）

1. 复制结构：`packages/docanon-engine-<kind>/pyproject.toml` + `src/docanon_engine_<kind>/`。
   **只许依赖 `docanon-contract` 与它自己的第三方**（不许依赖 core、不许依赖别的引擎）。
2. 在 `tests/test_architecture.py` 的 `ENGINES` 清单里登记（那份清单是故意写死的）；
   同步 `packages/docanon-core/pyproject.toml` 的依赖声明与 `requirements-dev.txt`。
3. 在 `tests/test_engine_portability.py` 里加参数：把"契约 + 这个引擎"拷到临时目录 import 一遍，
   并把其余包放成会抛异常的陷阱文件。
4. core 只许用它的**公开面**（`from docanon_engine_x import Y`），在 `config.py` 里像 ONNX/LLM 那样接线。
5. 写包级 `AGENTS.md`（本包边界/怎么测/本地坑），并在 `.agent/rules/02-packages.md` 的索引里加一行。

验证：

```bash
npm run test:py
.venv/bin/python -m pytest tests/test_architecture.py tests/test_engine_portability.py -q
```
