# AGENTS.md — docanon-engine-ocr

OCR 引擎：RapidOCR 包装（`ocr.py`）+ 图片/扫描页抽取（`image.py`，引擎名 `"ocr_image"`）。

- 只许依赖 `docanon-contract` + `rapidocr`/`onnxruntime`/`Pillow`，不许碰 core 或别的引擎。
- 扫描件 PDF 走这条路：**命中页整页栅格化**（安全保证，见 [`05-security.md`](../../.agent/rules/05-security.md)）。
- 测试：`packages/docanon-engine-ocr/tests/test_ocr.py`（真模型；缺依赖会 skip，所以必须用 `.venv/bin/python -m pytest`）。
- 可搬运性由 `tests/test_engine_portability.py` 真跑验证。

细则 → [`02-packages.md`](../../.agent/rules/02-packages.md)
