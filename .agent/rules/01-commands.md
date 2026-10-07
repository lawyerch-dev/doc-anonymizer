# 命令与脚本

**一律在仓库根执行。** 开发入口是 `./scripts/dev.sh <命令>`（只是包装，底层命令照旧可用）：

| 命令 | 做什么 |
|---|---|
| `setup` | 幂等：venv + 五个包 + 预览资源 + 字节码缓存重定向 |
| `web` | 起产品界面（默认 `-p 8000 -c configs/onnx.yaml`） |
| `desktop` | 起桌面壳（首次自动 `hutch install`） |
| `website` | 起官网/文档站（首次自动 `npm install`） |
| `test` | 跑测试（默认 `-q`） |
| `cli <参数>` | 直接调 docanon |
| `engines [配置]` | 这份配置实际加载了哪些引擎 |
| `models` | 取 ONNX 模型到 `var/models/onnx`（约 830MB，走 hf-mirror） |
| `doctor` | 环境自检：缺什么、为什么起不来 |

底层命令（排查时直接用）：

```bash
.venv/bin/python -m pytest -q                                     # 全量(约 5 秒)
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml   # 脱敏
.venv/bin/docanon engines -c configs/onnx.yaml                    # 引擎自检
.venv/bin/docanon restore var/out/x.md.redacted.md --mapping var/out/mapping.json
npm run build -w @doc-anonymizer/website                          # 官网静态站 → website/dist/
```

- 仓库**没有** lint / typecheck / CI / pre-commit，别顺手加（`apps/ui` 与 `website` 也刻意没装 eslint）。
- 各脚本干什么见 [`scripts/README.md`](../../scripts/README.md)。
