"""可移植引擎: 只依赖外部模型/推理库, 只许 import docanon.contract。

目录即边界(不再靠 tests 里的人工名单): 这个包下的任何 .py 都只许 import
`docanon.contract` 与 `docanon.engines.*`, 由 tests/test_architecture.py 机械检查。
要整块搬去别的项目, 把本目录 + contract.py 一起拷走即可。

内容:
  ocr.py        RapidOCR 包装(run_ocr), 无包内依赖
  ocr_image.py  图片抽取器(用 ocr.py)
  onnx_ner.py   ONNX 中文 NER 检测器
  llm/          本地大模型引擎: client.py(传输层) + ner.py(检测器)
"""
