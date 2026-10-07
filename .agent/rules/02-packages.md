# 包边界（Python 侧）

| 包 | 干什么 | 只许依赖 |
|---|---|---|
| `docanon-contract` | `Block`/`Span`/`Detection` + `Engine` ABC | 标准库 |
| `docanon-engine-ocr` | RapidOCR 包装 + 图片/扫描页抽取 | contract + rapidocr/onnxruntime/Pillow |
| `docanon-engine-ner-onnx` | ONNX 中文 NER（构造即加载） | contract + numpy/onnxruntime/tokenizers |
| `docanon-engine-ner-llm` | llama-server 客户端 + LLM NER | contract（传输层只用标准库） |
| `docanon-core` | 编排、脱敏回写、账本、CLI、Web | contract + 三个引擎 + pyyaml/pypdfium2/python-docx/openpyxl/Pillow |

每个包本地还有一份自己的 `AGENTS.md`（`packages/*/AGENTS.md`）：写它自己的边界、怎么测、本地坑。

方向永远是 **core → 引擎 → 契约**，由 `tests/test_architecture.py` 机械检查（含 pyproject 的依赖声明）。
core 内部再分层：`extractors/` → `detectors/` → `redaction/`，外加 `pipeline.py`/`job.py`/`server/`。

细则：

- **core 只许用引擎的公开面**（`from docanon_engine_x import Y`），不许 `from ...detector import`。
- 契约层只准 import 标准库，也**不许声明任何运行时依赖**（`dependencies = []` 被测试锁着）。
- **实体词表属于 app**：`DEFAULT_ONNX_ENTITY_MAP` 在 `docanon_core/config.py`，
  `OnnxNERDetector(model_dir, entity_map)` 当必填参数收；别把实体名写回引擎。
- **引擎参数属于引擎**：`LLMConfig` 住在引擎包里，app 反过来 import 它。
- 新引擎要实现 `capabilities()`（认识什么）与 `ready()`（起不来给原因）——`docanon engines` 与跑前预检
  都吃这两个自述；缺方法的默认值会让它在清单里显示"什么都不认识"，这是故意的。
- 加检测器 = 在 `docanon_core/detectors/base.py` 的 `DETECTORS` 登记一行 + 配置文件同名键打开。
  键名写错、或一个检测器都没开，都立刻报错，不许静默少一层。
- **可搬运性是被跑出来的**：`tests/test_engine_portability.py` 把"契约+单个引擎"拷到别处 import；
  新增引擎包要同步那份测试里的 `ENGINES` 清单。
- 不发布到包索引、也不用 entry points 发现引擎（发现失败 = 静默降级，与"少一层必须报错"冲突）。
