# doc-anonymizer

本地文档脱敏工具 —— 在 Apple Silicon Mac 上跑，中文优先。
输入文档 → 抽取文字(+坐标) → 规则/词典/大模型检测敏感信息 → 按类型替换 → 输出脱敏文件 + 映射表。

设计见 [docs/specs/2026-10-05-doc-anonymizer-design.md](docs/specs/2026-10-05-doc-anonymizer-design.md)。

## 技术栈

- **OCR**: RapidOCR 2.x (ONNXRuntime, PP-OCRv6 模型, 中文强、带坐标)
- **大模型**: llama.cpp (`llama-server`, OpenAI 兼容) + **Qwen3.8-4B-Distill** GGUF
  - 实测选型(见下表): 4B 蒸馏版召回 100%, 仅 3.1G 内存、1.46s/例, 胜过 9B
  - 量化 `Q4_K_M`(2.8G); 追求更省可换 Qwen3.5-4B / MiniCPM5-2B
  - 模型来源: ModelScope(国内直连 ~16MB/s)
- **CLI/Web**: Python 标准库 + 极简 Web, 无重依赖

## 安装

> 建议 Python 3.11/3.12。3.14 目前 onnxruntime/rapidocr 可能无轮子。

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[ocr,dev]'
```

## 下载并启动本地大模型

```bash
./scripts/download_model.sh Q4_K_M     # 从 ModelScope 下载 (~6 分钟)
./scripts/serve_llm.sh                 # 启动 llama-server :8080
# 另开一个终端, 打开 configs/default.yaml 里 detectors.llm_ner: true
```

## 快速开始

```bash
# 处理单个文件或目录
docanon run ./samples -o ./out -c configs/onnx.yaml

# 大卷宗跑到一半 Ctrl+C 或某个文件失败 —— 接着跑, 不重来
docanon run ./案件 -o ./out -c configs/onnx.yaml --resume

# 启动轻量 Web
docanon web --port 8000 -c configs/onnx.yaml

# 这份配置到底跑哪几层检测, 别猜(可用/不可用(带原因) + 实际能力)
docanon engines -c configs/onnx.yaml

# 还原(只支持文本产物, 见「已知限制」)
docanon restore ./out/sample.md.redacted.md --mapping ./out/mapping.json
```

`-c` 省略时走 `configs/default.yaml`：只有规则+词典（`onnx_ner`/`llm_ner` 均为 `false`），
同一个 `samples/example.txt` 实测会少掉 `PERSON` 与 `LOCATION`。**要人名/机构/地名就带上 `-c`。**
桌面壳固定用 `configs/onnx.yaml`；`docanon web` 得自己带上 `-c configs/onnx.yaml`。

示例文档由 `scripts/make_samples.py` 生成, 覆盖 txt/md/docx/pdf(文字)/pdf(扫描)/png/xlsx/csv。

### 产物与清单

产物命名 `<源文件全名>.redacted.<原扩展名>`, 并按源文件的相对路径建子树, 因此同名不同类型的文件不会互相覆盖:

```
docs/告知书/明细.docx   ->   out/告知书/明细.docx.redacted.docx
docs/债权人/明细.txt    ->   out/债权人/明细.txt.redacted.txt
```

| 源格式 | 产物 | 怎么脱敏 |
|---|---|---|
| docx | `x.docx.redacted.docx` | 按 run 改写文字, 保留格式与表格 |
| xlsx / csv | `x.xlsx.redacted.xlsx` / `x.csv.redacted.csv` | 改写单元格, 保留表结构 |
| pdf | `x.pdf.redacted.pdf` | 整页渲染成图后涂黑（**文字层没了**, 见「已知限制」） |
| png / jpg / tiff… | `x.png.redacted.png` | 按字符宽度比例（CJK=2/ASCII=1）只涂黑敏感片段 |
| txt / md / text | `x.txt.redacted.txt` | 按行替换纯文本 |

每次 run 还会更新两个文件(按源文件累加, 不覆盖上一次的记录 —— 同一个 `-o` 目录可以分批增量跑, 重复跑同一个文件只更新它那一条):

- `manifest.json` —— 每个源文件一条记录: `ok`(含产物路径与命中数) / `error`(含原因) / `unsupported`(格式不支持)。**只有 manifest 里标 `ok` 的文件才是脱敏过的。**
- `mapping.json` —— 原文↔脱敏值对照表, 含全部敏感信息原件, **切勿与脱敏文件一起外发**。

断点续跑: 清单与映射表**每处理完一个文件就落盘**(原子写), 所以几十页扫描件跑到一半 Ctrl+C 或崩掉,
已完成的部分不会丢、也不会被重做:

```bash
docanon run ./案件 -o ./out -c configs/onnx.yaml --resume
```

`--resume` 判定"这个文件已经脱过敏"的条件是账本里标 `ok` **且产物文件仍在** —— 账本说做过而文件不见了
(被删了、被移走了、或 `-o` 换了目录)会重做, 不会当成已完成。续跑要用同一个 `-o`, 否则路径核对不上。

退出码: `0` 全部处理; `2` 有文件未产出结果(格式不支持、抽取失败, 或跑到一半被中断); `1` 输入路径不存在、配置读不到、引擎起不来, 或 `-o` 目录里已有的清单/映射表读不出来(为不覆盖上次记录而拒绝执行)。

### 已知限制

- **pdf / 图片产物是涂黑位图**：前后可对比、可直接交付，但 PDF 的文字层没了（不可选中/搜索/再编辑），
  体积也变大。要可再编辑的产物请用 docx / xlsx / csv（原格式改写）。
- **docx 的页眉、页脚、脚注、文本框不抽取** = 不脱敏（正文段落与表格单元格已覆盖）。
- **`restore` 只支持文本产物**（txt/md/csv）。docx/xlsx/pdf/图片产物是原格式回写，没有可按映射表替换的
  纯文本；`remove` 策略删掉的原文没有锚点，无法还原（会明确提示有几条还原不了）。
- 打码后相同的值（两个号码都 mask 成同形）会还原成错的原文。
- `.doc` / `.xls` / `.wps` 暂不支持（清单里记 `unsupported` 并返回退出码 2）；GBK 编码的 CSV 需转成 UTF-8 再跑。
- 输出目录不要放在输入目录里面, 否则下一次 run 会把上一次的 `.redacted.*` 当成新文档再脱敏一遍。
- `mapping.json` 含全部敏感原文, 绝不与脱敏产物一起外发或提交。

> 混排 PDF（文字页 + 扫描页）**已支持**：逐页判断，有文字层的页按 charbox 涂黑，没有的页先 OCR 再涂黑。
> 扫描件质量差导致的 OCR 错字仍会传导到脱敏结果，所以原则是"召回优先"。

## 友好 Web 界面(推荐给非技术同事)

```bash
./scripts/fetch_file_viewer.sh                # 首次: 拉取 file-viewer 预览资源(约 232MB, 已 gitignore)
docanon web --port 8000 -c configs/onnx.yaml   # 浏览器打开 http://127.0.0.1:8000
```

流程：**左侧选内置示例(或上传) → 中间 file-viewer 预览原文 → 点「开始脱敏」→ 右侧同一查看器预览保留原格式的脱敏件**，并给出命中统计与下载。

- 预览基于 [file-viewer](https://github.com/flyfish-dev/file-viewer)（浏览器端只读预览，Apache-2.0）
- 脱敏**保持原格式**：docx→docx、xlsx→xlsx、pdf→pdf、图片→图片，便于左右对比
- 零构建：直接引用 file-viewer 预构建包，无 node 构建链
- 预览窗格铺满高度；默认**浅色模式**；已隐藏 file-viewer 自带工具栏（搜索/缩放/下载…），避免控件溢出
- 图片/扫描件按**字符宽度比例（CJK=2/ASCII=1）只涂黑敏感片段**，不再整行涂黑

### Web 接口

只监听 `127.0.0.1`，无鉴权（本地单机工具）。请求/响应都是 JSON（上传用 base64）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 单文件前端页面（`apps/web/index.html`） |
| GET | `/health` | `{ok, pid}` —— 桌面壳用它确认后端是自己拉起的那个 |
| GET | `/api/presets` | 内置示例清单 `{presets:[{name,url,size,preview}]}` |
| GET | `/samples/*`、`/file-viewer/*`、`/uploads/*`、`/outputs/*` | 静态资源（预置样例、预览器、上传件、脱敏产物） |
| POST | `/api/upload` | `{filename, content_b64}` → `{token, filename, url}`；上限 50MB |
| POST | `/api/anonymize` | `{preset}` 或 `{token}` → `{output_name, output_url, counts, kind, trace}`；`trace` 含 `extractor`/`detectors`/`timing`/`detections`（命中溯源） |

后端关掉了 HTTP 访问日志（`server.py` 的 `log_message` 是空实现）；排查问题看 `/api/anonymize` 返回的 `trace`，
前端「运行日志」弹窗消费的就是它。

## 桌面壳 (Electrobun, 可选)

把同一套 Web UI 装进原生窗口（macOS = 系统 WebView，不内置 Chromium，体积小一个数量级）。
**日常开发不用它** —— 直接 `docanon web` 用浏览器迭代更快。

```bash
curl -fsSL https://hutch.blackboard.sh/hutch/install.sh | sh   # 首次: 装 Hutch 工具链
cd apps/desktop
hutch install        # 装依赖(生成 hutch.lock)
npm start            # = hutch electrobun dev, 端口 8770
```

壳会拉起 `.venv` 的 Python 跑 `docanon web`，等 `/health` 就绪后开窗；后端起不来会打印原因并非零退出，
不留空窗口。三条实测约束（项目根按标记文件向上找、壳被强杀时后端自己了断、只认自己拉起的后端）
见 [apps/desktop/README.md](apps/desktop/README.md)。

## 多模型对比

```bash
./scripts/download_model.sh Q4_K_M          # 下载更多模型到 models/
.venv/bin/python scripts/bench_models.py    # 自动扫描 models/*.gguf 逐个跑基准
```

输出每个模型的 **召回率 / 平均耗时 / 内存**。测试样例见 `scripts/bench_models.py` 的 `CASES`。

### 已测基准 (Apple M5 / 32GB, 6 个中文样例, 12 个待识别片段)

| 模型 | 大小 | 召回 | 均耗时 | 内存 |
|---|---|---|---|---|
| **Qwen3.8-4B-Distill Q4_K_M** ✅默认 | 2.8G | 100% | 1.46s | 3.1G |
| Qwen3.5-4B Q4_K_M | 2.7G | 100% | 1.90s | 3.0G |
| Qwen3.5-9B Q4_K_M | 5.7G | 100% | 2.70s | 5.7G |
| MiniCPM5-2B Q4_K_M | 1.6G | 91.7% | 0.56s | 1.8G |
| Anonymizer-1.7B Q4_K_M | 1.1G | 91.7% | 0.62s | 1.6G |

> 6 例样本量小, 差距(100% vs 91.7%)仅 1 个未召回, 仅供参考; 扩大 `CASES` 可提高置信度。
> 专用脱敏模型 Anonymizer(英文训练)在中文上**未超过通用小模型**, 印证了"中文脱敏仍靠中文 LLM"。

## ONNX 路线(可选, 完全不依赖 llama.cpp)

用**编码器式中文 NER 模型**（ONNXRuntime 跑）替代生成式 LLM 做"理解"，更轻、更快、无需 server：

```bash
# 模型已下载到 models/onnx/ (gyr66 通用中文NER + pii-engineer 中文PII)
docanon run ./samples -o out_onnx -c configs/onnx.yaml
```

| 后端 | 召回 | 均耗时 | 依赖 |
|---|---|---|---|
| **ONNX 联合**(gyr66 + pii-engineer) + 规则 | **100%** | **34ms** | onnxruntime, 无 server |
| LLM Qwen3.8-4B | 100% | 1190ms | llama.cpp + 3G 模型 |

- 两个模型取并集：`gyr66` 出机构/人名，`pii-engineer` 出人名/手机/地址/身份证
- 金额由规则补（两个 NER 都无 AMOUNT 标签）
- 代价：标签集固定，不如 LLM 灵活（不能听指令、不能生成自然假名）

## 配置

见 [configs/default.yaml](configs/default.yaml)：敏感词表、各类型脱敏策略、LLM 地址。

- 配置里的相对路径(`onnx.model_dirs`、`-c` 的配置文件)按**仓库根/安装根**解析, 与你在哪个目录敲命令无关;
  打包成桌面应用后同一套规则成立(可用 `DOCANON_ROOT` 指定资源根)。命令行上的输入/输出路径仍按当前目录。
- 资源根是**找出来的, 不是猜出来的**: 从 `resources.py` 逐级向上找含 `configs/default.yaml` 的目录。
  找不到(例如 `pip install` 到了别处、不是 editable 安装)会直接报错并告诉你设 `DOCANON_ROOT`,
  而不是退回一个不存在的路径 —— 那样只会读到空配置, 看起来却像"引擎都没启用"。同理, 默认配置读不到
  (不带 `-c`)也报错, 不再静默退化。
- 检测引擎在 `detectors/base.py` 的注册表里按名字启用。引擎装不起来或端点没应答时, `run` 与 `web` 都会在
  写任何文件之前报错退出(退出码 1), 不会带着少一层检测的产物报告成功。
- 想确认"这份配置到底跑了几层检测", 别猜, 直接列出来:

  ```bash
  docanon engines -c configs/onnx.yaml   # 每个引擎: 可用/不可用(带原因) + 实际能力(实体类型或扩展名)
  ```
- ONNX 各模型标签 → 本项目实体类型的映射表在 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP`(app 侧词汇表);
  想在 yaml 里整表覆盖就写 `onnx.entity_map`。引擎本身不认识任何实体类型名, 映射表是它必填的构造参数。

## 目录结构

```
doc-anonymizer/
├── src/docanon/            # Python 包(CLI / Web / 桌面壳共用)
│   ├── contract.py         引擎契约: Block/Span/Detection + 引擎 ABC(只依赖标准库)
│   ├── engines/            ★ 可整块搬走的引擎(目录即边界): OCR / ONNX NER / LLM
│   ├── extractors/         抽取器(文本/PDF/表格) + 按扩展名路由
│   ├── detectors/          规则/词典检测器 + 注册表(base.py)
│   ├── inventory.py        引擎自检清单(`docanon engines`)
│   ├── resources.py        资源根 + 仓库布局表(所有相对路径的唯一出处)
│   ├── writers.py          原位回写(docx/xlsx/csv/pdf/图片)
│   ├── strategies.py       脱敏策略(pseudonym/placeholder/mask/remove)
│   ├── resolve.py          重叠合并
│   ├── mapping.py          全局映射表(全文一致 + 可还原)
│   ├── job.py              账本: manifest/mapping 每文件原子落盘, --resume 的依据
│   ├── pipeline.py         编排: 抽取 → 检测 → 合并 → 替换 → 回写
│   ├── server.py           本地 HTTP 服务(前端/桌面壳共用)
│   └── cli.py              命令行(run / restore / engines / web)
├── apps/
│   ├── web/                前端: 单文件 index.html + vendor/file-viewer(232MB, gitignore)
│   └── desktop/            Electrobun 桌面壳: src/bun 主进程 + compat/ WebKit 兼容检查
├── configs/                配置(default / onnx / with_llm)
├── scripts/  samples/  tests/  docs/
└── models/                 模型权重(gitignore)
```


## 非目标

不依赖 Ollama / 云端；不做完美版式还原，不做多用户与权限系统（可还原的映射表先用本地文件，
见[设计方案](docs/specs/2026-10-05-doc-anonymizer-design.md) §6）。
