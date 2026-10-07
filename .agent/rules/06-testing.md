# 测试与守卫

**必须用 `.venv/bin/python -m pytest`**：PATH 上的 `pytest` 可能跑在别的 Python 上（缺 `rapidocr`），
那样扫描件测试会被静默 skip —— OCR 回归等于没测。全量约 5 秒。

守卫测试分工（改代码前知道谁在盯你）：

| 文件 | 盯什么 |
|---|---|
| `tests/test_architecture.py` | 包边界、pyproject 依赖声明、引擎包清单 |
| `tests/test_engine_portability.py` | 引擎能被拷走独立 import（带陷阱文件反证） |
| `tests/test_docs.py` | 文档路径/链接/测试数量/一个主题一个出处/组件复用/文档站接线/`.agent` 索引/`npm scripts` 都被 README 写到/组件库完整性/Tailwind `@source` 有效 |
| `tests/test_dev_env.py` | 源码树不许有 `__pycache__`、`scripts/*.sh` 可执行、缓存重定向钩子 |
| `packages/docanon-core/tests/` | 布局、资源根、产物命名、账本、PDF、还原、服务生命周期 |
| `packages/docanon-*/tests/` | 各引擎自己的语义（词表必填、缺模型要报错、真模型上跑一遍） |

- **改测试要同步 `AGENTS.md` 里那句"N 项"**，否则 `test_docs.py` 会红（故意的）。
- 浏览器端 WebKit 检查在 `tests/e2e/webkit/`（node + Playwright，**不进 pytest**，需手动跑）：

```bash
.venv/bin/docanon web -p 8803 -c configs/onnx.yaml &
cd tests/e2e/webkit && DOCANON_URL=http://127.0.0.1:8803 node webkit-check.mjs   # errors 必须是 []
```
