# Web 脱敏配置（分层可编辑口径）— 设计方案

- 日期: 2026-10-08
- 状态: 待评审
- 相关: [2026-10-08 旧格式转换](2026-10-08-legacy-office-conversion-design.md) ·
  [README 用法](../../README.md) · 细则规则 [`.agent/rules/07-frontend.md`](../../.agent/rules/07-frontend.md)

## 1. 背景与目标

现状：Web 的"配置"只是**选一个 `configs/*.yaml`**，下拉标签取文件首行注释——等于把"配置文件选择器"
当成"配置功能"。用户无法表达真正关心的东西：某个类型要打码还是盖掉、要不要用假名、加自己的敏感词、
换一个 ONNX 模型。用户看到"公司名变成像真的假名"会以为没脱敏；想微调只能去改仓库里的 yaml。

目标：**围绕"脱敏"这一步，给 Web 一个分层、可保存、可分享的配置体验**，且默认不吓人、想钻的人能钻到底。

成功判据：不离开浏览器即可（1）从模板或内置预设起步，（2）逐类型设定策略并看到效果示例，
（3）加自定义敏感词，（4）按需开关检测器/换模型，（5）改完**直接试跑**，满意后命名保存、导出成 yaml 分享。

## 2. 非目标（YAGNI）

不做：OCR 开关（关掉 = 静默少一层覆盖，违反"少一层必须报错"）；产物命名选项（是契约不是偏好）；
逐文件不同口径；鉴权/多用户；patch 式（base+增量）配置；写回仓库 `configs/`；配置的实时"前后对照预览"
（沿用既有的一次运行结果对比）。

## 3. 数据模型

### 3.1 三类对象

| 对象 | 位置 | 可改 | 说明 |
|---|---|---|---|
| 内置预设 | `configs/*.yaml`（在仓库） | 否（只读） | 现有 `default/onnx/llm/legal` |
| 用户配置 | `var/configs/<name>.yaml` | 是 | 与内置**同 schema**；`var/` 已 gitignore |
| 模板 | 内置常量（不落盘） | 否 | 松/标准/严/法律交付件；选中即预填矩阵 |

用户配置直接复用现有 yaml schema 与 `docanon_core.config.load_config`，**不引入新的配置模型**：

```yaml
strategies: { PHONE: mask, PERSON: redact, ORG: redact, ..., DEFAULT: redact }
dictionary: [内部项目代号, ...]
detectors:  { rule: true, dictionary: true, onnx_ner: true, llm_ner: false }
onnx:       { model_dirs: [var/models/onnx/gyr66, ...] }
llm:        { base_url: http://127.0.0.1:8080/v1, model: qwen3.8-4b }
legacy_convert: true
```

### 3.2 引用规则

- 内置预设引用 = `onnx.yaml`（**带扩展名**）。
- 用户配置名 = `^[A-Za-z0-9_-]{1,32}$`（**不含点**），因此天然不与内置撞名，也杜绝路径穿越。
- 同名不同类由扩展名区分：见 `…yaml` 走内置，其余走 `var/configs/`。

### 3.3 模板与"假名开关"

- 模板（松/标准/严/法律交付件）只提供**起始策略矩阵**；应用后矩阵是唯一真相，用户改矩阵即改结果。
- "用假名替代人名/机构"是一个把 `PERSON`/`ORG` 在 `redact`（`**`）与 `pseudonym`（可信假名）之间批量
  切换的快捷开关；它只改矩阵，不引入第二种表达。

## 4. 后端接口

校验与落盘集中在**新模块** `packages/docanon-core/src/docanon_core/server/profiles.py`
（纯函数 + 文件读写，可独立测试）；`routes.py` 只做 HTTP 胶水。

| 方法 | 路径 | 作用 | 备注 |
|---|---|---|---|
| GET | `/api/configs` | 列出内置+用户：`{name,label,kind,current}` | `kind ∈ {builtin,user}` |
| GET | `/api/configs/{ref}` | 取一份的可编辑结构 | 见 §3.3 schema 的子集 |
| PUT | `/api/configs/{name}` | 校验后原子写 `var/configs/<name>.yaml` | 名字须匹配 §3.2 |
| DELETE | `/api/configs/{name}` | 删用户配置；**拒删内置** | |
| GET | `/api/configs/{name}/export` | 下载该 yaml | `Content-Disposition: attachment` |
| POST | `/api/configs/import` | `{filename, content_b64}` → 校验 → 存为用户配置 | 名字从 filename 取并校验 |
| GET | `/api/models` | `{onnx_dirs:[…]}`（扫 `var/models/onnx/*`）+ `{llm:{base_url,model}}` 默认 | 供 L3 下拉 |
| POST | `/api/anonymize` | body `{preset\|token, config}` | `config` 可为**内联对象**或配置名 |

`/api/anonymize` 的 `config` 兼容：字符串 = 配置名（旧行为，保留）；对象 = 完整可编辑结构（内联试跑）。

## 5. 校验与安全

- **结构校验**（保存与内联运行都过）：
  - `strategies[*] ∈ {redact, mask, placeholder, pseudonym, remove, keep}`；
  - `detectors` 键 ⊆ `{rule, dictionary, onnx_ner, llm_ner}`，值为布尔，至少一个为真（否则报"没有启用的检测器"）；
  - `dictionary` 为字符串列表；`onnx.model_dirs` 为字符串列表；`llm.base_url`/`llm.model` 为字符串。
- **引擎预检在"运行"时做**（沿用 `prepare_detectors`）：缺 ONNX 模型 / LLM 连不上 → **400 + 原因**，
  绝不静默少一层。列表接口**不**预检（避免每次请求加载 ONNX）。
- 落盘只进 `var/configs/`，**原子写**（临时文件 + `os.replace`）；拒改内置；读取一律 `yaml.safe_load`。

## 6. 前端分层 UI（渐进披露）

- **L1 口径**：下拉（内置预设 + 我的配置）+ `新建` / `另存为` / `导出` / `导入`；右侧显示当前口径名。
- **L2 自定义脱敏**（展开）：`用假名替代人名/机构` 开关 · **逐类型策略表**（每行：类型 / 策略下拉 /
  **效果示例**，如 `138****0000`、`**`、`<PHONE_1>`、`林芳`）· 自定义敏感词（chips 输入）。
- **L3 检测引擎**（再展开）：4 个检测器勾选 · ONNX 模型目录多选 · LLM 地址 / 模型名。
- 交互：**改完直接"开始脱敏"用内联配置试跑**，满意再 `保存`/`导出`——不必先存盘。
- 仅当 L2/L3 被改动才展开/高亮，避免默认糊一堆选项给普通用户。

## 7. 运行与预检语义

- 运行 = 用**当前编辑器内容**（内联对象）构造 `Config` → `prepare_detectors` 预检 → `process_file`。
- 保存 = 仅结构校验通过即写盘；**不**因本机缺模型而拒绝保存（换台机器/后补模型仍可用）。
  运行该配置时若引擎不可用，按 §5 返回 400 + 原因。
- `trace` 增加：`config`（用了哪份/`inline`）与既有 `converted_from` 并列。

## 8. 兼容性

- `GET /api/configs` 与 `config` 入参是**新增**；`/api/anonymize` 仍接受 `config` 为字符串（旧客户端不破）。
- 现有 `configs/*.yaml` 与 `load_config` 不变；用户配置只是"同 schema 的另一份文件"。
- `var/configs/` 落在已 gitignore 的 `var/` 下，无需改 `.gitignore`；不是 `resources.LAYOUT` 的资源项
  （用户资产，非随包资源），但从 `resources.root()` 拼 `var/configs` 以保证与资源根一致。

## 9. 测试

- **单测（profiles 模块）**：名字规则（拒 `..`、拒内置撞名）、结构校验各失败分支、存读往返、
  导入导出往返、删用户成功/删内置被拒。
- **server 测试**：`GET /api/configs` 合并内置+用户并标当前；`GET/PUT/DELETE` 往返；
  内联对象跑通；非法策略值/非法名字/检测器名未知 → 400；检测器开着但模型缺失 → 400 + 原因；
  内联 `config` 为字符串（旧行为）仍工作。
- 不新增前端 JS 测试（仓库无 JS 单测链）；前端改动以 `node --check` + 现有文档站构建 + 手工核对为准，
  在计划里列为手工验证项。

## 10. 文档同步

- `README.md` / `README.en.md`：Web 章节补 `/api/configs`、`/api/models`、`config` 入参、分层说明与 `var/configs/`。
- `.agent/rules/07-frontend.md`：新增"Web 配置面（内置/用户配置、分层、预检语义）"一节。
- `CHANGELOG.md`：记一条。
- `.agent/notes/implemented/`：留决策笔记（为什么用户配置放 `var/`、为什么 A 层是模板）。
- 跑 `python3 website/scripts/sync-content.py --record-hashes`（README 双语配对）。
- 测试数变化 → 同步根 `AGENTS.md` 的「（N 项，约 M 秒）」。

## 11. 风险

- **运行期改检测器要加载引擎**：首次启用 ONNX 会有秒级加载；LLM 需 `health` 探测。预检失败必须清晰
  报错，不能让人以为"点了没反应"。
- **yaml 手写风险**：导入的 yaml 可能带非法策略值/未知检测器名——靠 §5 结构校验挡住，报错要点名。
- **浏览器本地记忆与文件不同步**：运行用内联内容、保存才落盘；UI 要明确"未保存"状态，避免以为已存。
- **`**` 与 `restore`**：常量替换无法唯一还原，属既有免责（同形 mask 也如此），文档已列。
