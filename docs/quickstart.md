# 快速上手

前置：Apple Silicon macOS + Python 3.11/3.12；命令都在仓库根执行。
一键入口与完整用法见 [README](../README.md#快速上手)。

## 1. 装

```bash
npm run setup      # 一键装齐: Python venv + 五个包 + 预览资源 + npm install
npm run doctor     # 确认: 工具链/预览资源/ONNX 模型 + 这份配置加载了哪些引擎
```

`doctor` 里任何"不可用"都先解决它再往下走 —— 本项目宁可报错，也不产出少一层检测的文件。
报 `onnx_ner` 缺模型就取一次：`npm run models`（约 830MB，走 hf-mirror 镜像）。

## 2. 跑一份文档

```bash
npm run cli -- run ./samples -o var/out -c configs/onnx.yaml
ls var/out          # sample.docx.redacted.docx  manifest.json  mapping.json  …
```

- 产物同格式、保留子目录；`manifest.json` 里**只有 `ok` 是脱敏过的**；
- `mapping.json` 含全部原文，**不要外发**。

换自己的文件：把 `./samples` 换成文件或目录（输出目录**不要**放在输入目录里面）。

## 3. 界面

```bash
npm run dev                 # → http://127.0.0.1:8000（官网/文档站: npm run dev:website）
```

选示例或上传 → 看原文 → 脱敏 → 对照；「运行日志」是逐条命中溯源。

## 4. 断了接着跑 / 还原

```bash
npm run cli -- run ./案件 -o var/out -c configs/onnx.yaml --resume
npm run cli -- restore var/out/sample.md.redacted.md --mapping var/out/mapping.json -o restored.md
```

`--resume` 的判定是「清单标 `ok` **且产物文件还在**」。`restore` 只吃 txt/md/csv；
`remove` 删掉的原文没有锚点，还原不了。

## 5. 换检测路线

| 想要 | 配置 | 额外准备 |
|---|---|---|
| 只要规则 + 词典（最快） | `configs/default.yaml`（不带 `-c` 就是它） | 无 |
| 人名/机构/地址（日常推荐） | `-c configs/onnx.yaml` | `npm run models` |
| 更灵活的实体识别 | `-c configs/llm.yaml` | `./scripts/download_model.sh` + `./scripts/serve_llm.sh` |

## 常见问题

- **预览区空白** → 没拉预览资源：`./scripts/fetch_file_viewer.sh`。
- **报资源根/缺前端页面** → 非 editable 安装：设 `DOCANON_ROOT=/path/to/doc-anonymizer`。
- **某个引擎不可用** → 看它给的原因（ONNX 缺模型 / LLM 没起 server）；也可先把它在配置里置 `false`。
- **退出码 2** → 有文件没产出结果：看 `manifest.json` 里的 `error` / `unsupported`，不是跑坏了。
- **漏检** → 确认带了 `-c configs/onnx.yaml`（不带只有规则+词典，实测少人名与地名）；
  把关心的词加进配置的 `dictionary`。**不保证零漏检**，详见 [README「已知限制」](../README.md#已知限制)。
