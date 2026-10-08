# 命令与脚本

**一律在仓库根执行，入口是 npm scripts**（`npm run <命令>`）。`scripts/dev.sh` 是实现层
（处理 venv 检查、资源提示等），直接用也可以，但文档与 CI 一律写 npm：

| 命令 | 做什么 |
|---|---|
| `npm run setup` | 一键装齐：Python venv + 五个包 + 预览资源 + 字节码缓存重定向 + `npm install` |
| `npm run dev` | 起产品界面（默认 `-p 8000 -c configs/onnx.yaml`） |
| `npm run dev:website` | 起官网/文档站 → :4321 |
| `npm run dev:desktop` | 起桌面壳（首次自动 `hutch install`） |
| `npm test` | 一键全测：Python 全量 + 组件库导入检查 + 文档站构建 |
| `npm run test:strict` | 反假绿：声明环境齐备后**任何 skip 都算失败**（装了模型的机器/发版本前跑） |
| `npm run check:scope` | 按改动范围算出**最小**该跑的检查（不是无脑全量；详见 06-testing） |
| `npm run test:py` / `test:web` | 只跑其中一半 |
| `npm run build` | 构建静态站 → `website/dist/` |
| `npm run cli -- <参数>` | 直接调 docanon（注意 npm 的 `--`） |
| `npm run engines` / `models` / `doctor` | 引擎自检 / 取模型 / 环境自检 |

底层命令（排查时直接用）：

```bash
.venv/bin/python -m pytest -q                                     # 全量(约 5 秒, = npm run test:py)
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml   # 脱敏
.venv/bin/docanon engines -c configs/onnx.yaml                    # 引擎自检
.venv/bin/docanon restore var/out/x.md.redacted.md --mapping var/out/mapping.json
npm run build                                                     # 官网静态站 → website/dist/
```

- 仓库**没有** lint / typecheck / CI / pre-commit，别顺手加（`packages/ui` 与 `website` 也刻意没装 eslint）。
- 各脚本干什么见 [`scripts/README.md`](../../scripts/README.md)（`dev.sh` 是实现层，npm scripts 调它）。
