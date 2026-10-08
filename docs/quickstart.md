[English](quickstart.en.md) | 中文

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
| **交出去的材料**（只抹身份证/银行卡/手机/住址，机构、人名、角色、日期、金额一律不动） | `-c configs/legal.yaml` | `npm run models`（只为了取地址） |
| 人名/机构也一起换（对外讲课、写案例） | `-c configs/onnx.yaml` | `npm run models` |
| 更灵活的实体识别 | `-c configs/llm.yaml` | `./scripts/download_model.sh` + `./scripts/serve_llm.sh` |

**选哪份取决于材料要不要能用**：`onnx.yaml` 会把法院、律所、当事人姓名、判决日期也换掉，
判决书/裁定书这类材料抹完就没法提交了；交付场景用 `configs/legal.yaml`（它把不能动的类型全设成
`keep`，见 [README「配置」](../README.md#配置)）。

## 常见问题

- **预览区空白** → 没拉预览资源：`./scripts/fetch_file_viewer.sh`。
- **报资源根/缺前端页面** → 非 editable 安装：设 `DOCANON_ROOT=/path/to/doc-anonymizer`。
- **某个引擎不可用** → 看它给的原因（ONNX 缺模型 / LLM 没起 server）；也可先把它在配置里置 `false`。
- **退出码 2** → 有文件没产出结果：看 `manifest.json` 里的 `error` / `unsupported`，不是跑坏了。
- **该抹的没抹（漏检）** → 只用 `configs/default.yaml` 时没有人名/地名识别，这是设计；但**交付件本来
  也不该抹人名机构**，漏检重点看扫描件的 OCR（认错字就不会命中）。把关心的词加进配置的 `dictionary`。
  **不保证零漏检**，详见 [README「已知限制」](../README.md#已知限制)。
- **抹多了、材料不能用了** → 你在用 `onnx.yaml`；交付场景换 `-c configs/legal.yaml`。
