# 5 分钟快速上手

命令都在仓库根执行。前置：Apple Silicon macOS + Python 3.11/3.12
（3.14 目前装不上 `onnxruntime`）。

## 1. 开发者：一条命令

```bash
git clone https://github.com/lawyerch/doc-anonymizer && cd doc-anonymizer
./scripts/dev.sh setup      # venv + 五个包 + 预览资源 + 缓存重定向, 末尾附自检
./scripts/dev.sh web        # → http://127.0.0.1:8000
./scripts/dev.sh desktop    # 桌面壳(系统 WebView), 需要 Hutch
./scripts/dev.sh test       # 跑测试
```

| 命令 | 做什么 |
|---|---|
| `./scripts/dev.sh setup` | 一条命令装好环境（幂等）：venv + 五个包 + 预览资源 + 缓存重定向，末尾附环境自检 |
| `./scripts/dev.sh web` | 起 Web 界面（默认 `-p 8000 -c configs/onnx.yaml`） |
| `./scripts/dev.sh desktop` | 起桌面壳（系统 WebView；首次自动 `hutch install`） |
| `./scripts/dev.sh test` | 跑测试（默认 `-q`） |
| `./scripts/dev.sh cli <参数>` | 直接调 docanon |
| `./scripts/dev.sh engines [配置]` | 这份配置实际加载了哪些引擎 |
| `./scripts/dev.sh doctor` | 环境自检：缺什么、为什么起不来 |

`dev.sh` 只是包装，底层还是下面这些原始命令；出问题时可以直接用它们排查。

`setup` 与后续命令都是幂等的；`doctor` 会打印 venv / 五个包 / 预览资源 / ONNX 模型的现状，
以及 `configs/onnx.yaml` 实际加载了哪些引擎 —— **哪一层起不来、为什么，先看它**。
本项目宁可报错也不产出"少一层检测"的文件。

## 2. 使用者：处理第一份文档

先确认真模型都在（每个引擎一行：`可用` 或 `不可用: <原因>`）：

```bash
./scripts/dev.sh engines
```

碰到"不可用"先解决它再往下走。然后跑仓库自带的 `samples/`
（虚构数据，覆盖 txt/md/docx/pdf/扫描件/图片/xlsx/csv）：

```bash
./scripts/dev.sh cli run ./samples -o var/out -c configs/onnx.yaml
```

看输出目录：

```bash
ls var/out
#  sample.docx.redacted.docx   sample_scan.png.redacted.png   manifest.json   mapping.json  ...
```

- 产物保留原格式，名字是 `<源文件名>.redacted.<原扩展名>`，子目录结构照搬；
- `manifest.json` 记每个文件是 `ok` / `error` / `unsupported` —— **只有 `ok` 才是脱敏过的**；
- `mapping.json` 里有全部敏感原文，**不要和脱敏件一起外发**（它是给 `restore` 用的）。

换成你自己的文件：把 `./samples` 换成一个文件或目录即可（输出目录**不要**放在输入目录里面）。

## 3. 打开界面

```bash
./scripts/dev.sh setup            # 首次会把预览资源一起拉下来(约 232MB, 已 gitignore)
./scripts/dev.sh web              # → http://127.0.0.1:8000
```

浏览器打开 <http://127.0.0.1:8000>：左侧选示例或上传 → 中间看原文 → 点「开始脱敏」→ 右侧看脱敏件。
顶栏「运行日志」里是逐条命中溯源：哪个引擎、在哪个位置、命中了什么、替换成了什么。

## 4. 大卷宗跑一半断了

账本每处理完一个文件就落盘，所以直接续跑（**必须用同一个 `-o`**）：

```bash
./scripts/dev.sh cli run ./案件 -o var/out -c configs/onnx.yaml --resume
```

判定"已脱敏"的条件是"清单里标 `ok` **且产物文件还在**"：产物被删/被移走会重做，不会当成已完成。

## 5. 还原

只支持文本产物（txt/md/csv）：

```bash
./scripts/dev.sh cli restore var/out/sample.md.redacted.md --mapping var/out/mapping.json -o restored.md
```

提示"有 N 条原文是 remove 策略删掉的"是正常的：被整段删掉的原文没有锚点，无法还原。

## 6. 换成别的检测路线

| 想要 | 用哪份配置 | 额外准备 |
|---|---|---|
| 只要规则 + 词典（最快） | `configs/default.yaml`（不带 `-c` 就是它） | 无 |
| 人名/机构/地址（日常推荐） | `-c configs/onnx.yaml` | 无（仓库根 `var/models/onnx/` 需有模型） |
| 更灵活的实体识别（可听指令） | `-c configs/llm.yaml` | `./scripts/download_model.sh` 然后 `./scripts/serve_llm.sh` |

模型从哪来、为什么默认选这个：[docs/benchmarks.md](benchmarks.md)。

## 常见问题

**预览区一片空白？** 没拉预览资源，跑 `./scripts/fetch_file_viewer.sh`（缺它时所有 `/file-viewer/*` 都 404）。

**Web 起不来，报"缺前端页面"或"资源根"？** 说明资源根没找对：正常是从代码逐级向上找含
`configs/default.yaml` 的目录；非 editable 安装（`pip install` 到别处）请设
`DOCANON_ROOT=/path/to/doc-anonymizer`。

**某个引擎"不可用"？** 先看它给的原因：ONNX 多半是 `var/models/onnx/` 下没模型；LLM 是
`llama-server` 没起。也可以先只用能用的那层（把 `detectors` 里起不来的那个置 `false`）。

**跑完退出码是 2？** 表示清单里有文件没产出结果（格式不支持/抽取失败/被中断）。看
`var/out/manifest.json` 里那些 `error` / `unsupported` 条目，别当成"跑坏了"。

**一堆敏感词没被识别？** 确认你带了 `-c configs/onnx.yaml`（不带 `-c` 只有规则+词典，
实测会少掉人名与地名）；再把你关心的词写进配置的 `dictionary`。

**能保证不漏吗？** 不能。它是"召回优先 + 人工复核"的辅助工具：OCR 错字、罕见写法都可能漏，
交付前请人工过一遍（见 README「已知限制」）。
