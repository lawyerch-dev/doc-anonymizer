# 竞品分析：本地离线文档脱敏工具（2026-10-14）

> 目的：为 v0.7+ 功能规划提供输入。方法：官网一手信息（P0）逐页抓取 + 仓库代码核实自家能力。
> 数据截止：2026-10-14。价格与功能宣称均来自竞品官网，属其单方宣称，未实测验证。

## 一、结论速览

1. **市场格局：碎片化起步期**。国内已有 3 家定位几乎相同的商业产品（LawRedact、零信脱敏、律隐盾），价格带趋同于 **¥299–¥588 买断 + 1 年更新**，说明定价共识已形成，窗口期仍在。
2. **我方位置**：唯一的 **MIT 开源 + 三入口（CLI/Web/桌面）** 产品，识别引擎层数（规则+ONNX+LLM 可插拔）不落后；但 **缺人工复核工作台**，这是三家商业竞品的共同标配，也是付费流程的核心环节。
3. **Top 3 行动**（详见 §5）：① 复核工作台（命中列表 + 误报排除 + 补标）；② 跨文档代号一致（项目/案件级假名词典）；③ 审计报告导出（把已有账本升级为对外合规报告）。

## 二、竞品概览

| | LawRedact 脱敏大师 | 零信脱敏 | 律隐盾 | Microsoft Presidio | 本项目 doc-anonymizer |
|---|---|---|---|---|---|
| 定位 | 法律全场景工作站 | 通用高敏材料 | 法律轻量复核流 | 开源 PII 框架（非成品） | 中文法律文档，开源 |
| 价格 | ¥388 / ¥588 桌面买断，移动 ¥128，iOS 免费 Lite，更新 ¥99/年 [cite:1][cite:3] | 单设备 ¥299、双设备 ¥569 永久，含 1 年更新；服务器版另报价 [cite:4] | ¥1 试用 7 天、单台 ¥389 永久 [cite:5] | 免费（Apache-2.0） | **MIT 开源免费** |
| 交付形态 | 桌面 + Android/Harmony/iOS Lite | 桌面（Win/Mac/Linux/信创）+ 服务器 Docker API [cite:4] | 仅桌面（Win/Mac ARM）[cite:5] | Python 库/服务 | CLI + Web + 桌面（Win/macOS） |
| 准确率宣称 | F1 99.73%（自研 LROLMLL 3.0）[cite:1] | 中文严格 F1 98.25%、覆盖率 99.26% [cite:4] | 未公布 | — | 基准数字见 docs/benchmarks.md |
| 实体类型 | 45 类、中英日韩 [cite:1] | 30+ 类 + 自定义规则，中英 [cite:4] | 15 类 + AI 自定义语义类型 [cite:5] | 预定义 recognizers（regex+NER）[cite:6] | 规则类（号码/邮箱/词表）+ NER（人名/机构/地址）+ 可选 LLM；中文优先 |

## 三、功能对比矩阵

图例：✅ 完整 · ⚠️ 部分 · ❌ 无。本列依据仓库源码与 README（路径已核实）；竞品列依据官网宣称。

| 功能 | 本项目 | LawRedact [cite:1][cite:2] | 零信 [cite:4] | 律隐盾 [cite:5] |
|---|---|---|---|---|
| **输入格式** | | | | |
| docx / pdf / xlsx / csv / txt / md | ✅ | ✅ | ✅ | ✅ |
| 扫描件 OCR + 图片脱敏 | ✅ RapidOCR | ✅ 流式 OCR | ✅ 含旋转矫正 | ✅ 含倾斜/模糊增强 |
| 旧版 Office（doc/xls/wps） | ✅ 经 LibreOffice 转换 | ❓未提 | ✅（导出转 docx/xlsx） | ❓未提 |
| PPT / CAD / 剪贴板 / 加密文件 | ❌ | ❌ | ✅ PPT、CAD、剪贴板、密码文件 | ⚠️ 密码文件 |
| 音视频转写脱敏 | ❌ | ✅ | ❌ | ❌ |
| **识别与策略** | | | | |
| 引擎分层 | ✅ 规则 + ONNX 小模型 + 本地 LLM 三层可插拔 | 自研大模型 | 自研（4GB 内存可跑） | 本地语义模型 |
| 策略种类 | ✅ 6 种：anchor/placeholder/pseudonym/mask/redact/remove | 4 种：假名/星号/涂色/删除 | 4 种：代号/中部掩码/完全掩码/擦除留白 | 3 种：星号/黑块/占位 |
| 按实体类型配策略 | ✅（L2 逐类型） | ✅ 模板 | ✅ | ✅ |
| 自定义规则（正则/通配符/图形） | ⚠️ 词表级 | ⚠️ 模板级 | ✅✅ 含图形匹配、表头规则、Excel 批量导入 | ✅ 黑白名单 + 自定义语义类型 |
| **可逆还原** | | | | |
| 锚点还原 | ✅ 默认策略（anchor） | ✅（文档级/项目级 + 任务中心） | ✅ 代号还原 + 代号表导入 | ❌ 未提 |
| 还原入口 | ✅ CLI + Web 批量（界面标记开发中） | ✅ | ✅ | — |
| **复核与批量**（最大差距区） | | | | |
| 人工复核工作台 | ❌ | ✅ 误报修正/补录/假名纠正/防漏提示 | ✅ 命中列表/搜索补标/批量标注 | ✅✅ 低置信集中复核/同文复核/并排对比/区域遮蔽 |
| 质量评分 | ❌ | ✅（80 分建议外发） | ⚠️ 命中项列表 | ❌ |
| 审计/合规报告 | ⚠️ 账本 manifest + mapping.json | ✅ JSON 合规报告 | ✅ 代号表/命中项列表导出 | ⚠️ 诊断包 |
| 批量处理 | ✅ 文件夹批 + 账本 + --resume | ✅ 案件批量 | ✅ 项目制（追加/子目录扫描） | ✅ 含任务队列（取消/重试） |
| **跨文档代号一致**（同一案件多文件同假名） | ⚠️ 仅单文档内一致 | ✅ 共享假名词典 | ✅✅ 项目制 + 沿用历史项目 | ✅ 分组共用 |
| **平台** | | | | |
| Windows / macOS | ✅ / ✅ | ✅ / ✅ | ✅ / ✅（含 Intel） | ✅ / ✅ |
| Linux / 信创 | ❌ | ❌ | ✅✅ UOS/麒麟/飞腾/鲲鹏 | ❌ |
| 移动端 | ❌ | ✅ Android/Harmony/iOS Lite | ❌ | ❌ |
| 服务器部署 / API | ⚠️ 本机 Web 服务 | ❌ | ✅ Docker + HTTP API | ❌ |

## 四、定位判断

以「识别-复核-交付工作流完整度」与「场景覆盖宽度」两维看：

| 象限 | 产品 |
|---|---|
| 工作流深 × 场景宽 | 零信脱敏（含服务器版、信创、CAD） |
| 工作流深 × 场景聚焦法律 | LawRedact（含移动端、音视频） |
| 工作流较深 × 单机轻量 | 律隐盾 |
| 框架层（需自建工作流） | Presidio |
| **本项目** | 引擎强（多层可插拔 + 可还原默认）、**工作流断在"复核"环节** |

关键洞察：三家商业产品 100% 都做了**复核工作台 + 跨文档一致性**，没有任何一家省略——这是用户从"敢不敢外发"到"敢外发"的信任闭环，而非可选项。

## 五、差异化打法

**Catch-up（必须补齐，按优先级）**

| 优先级 | 功能 | 依据 |
|---|---|---|
| P0 | 复核工作台：命中列表 + 原文定位 + 误报排除 + 搜索补标 | 三家全有；我们已有 anchor/账本地基，Web 端补 UI 即可 |
| P0 | 跨文档代号一致：案件级共享假名词典 | 已有批量骨架（routes.py batch），缺跨文件词典复用 |
| P1 | 审计报告导出：manifest+mapping 升级为对外 JSON/PDF 合规报告 | LawRedact 以此作为 B 端卖点 |
| P1 | 自定义规则升级：正则 + 黑白名单 + Excel 批量导入 | 零信把它做成了明显的差异化壁垒 |
| P2 | 低置信集中复核 / 质量评分 | 律隐盾、LawRedact 的信任设计 |

**Differentiate（守住并放大）**

1. **MIT 开源 + 全离线**：唯一开源产品，政务/信创采购中"可审计源码"是硬资质；商业产品闭源无法跟进。
2. **anchor 可寻址还原为默认**：三家还原均为增值功能或缺失，我们默认可逆。
3. **CLI 三入口同引擎**：自动化脚本、CI 内嵌、批量管道场景三家均无。
4. **LLM 可插拔 + 确定性护栏**：规则兜底（不靠提示词）的设计已在真合同上验证过误伤问题。

**Innovate（竞品未做）**

- 结合用户已有能力：把「还原任务中心」做成 CLI 工具链（配合脚本化场景，商业产品均无 CLI）。
- 面向开源生态的 Presidio 识别器兼容层（复用其 community recognizers，低成本扩实体）。

## 六、LawRedact 移动端实现拆解（一手证据）

数据取自 App Store 公开元数据、小米应用商店详情、其官方 Android 隐私政策与 8 张 App Store 实机截图（均 2026-10-14 获取）。

### 6.1 事实层

| 项 | 事实 | 来源 |
|---|---|---|
| iOS | Bundle `com.lawredact.app`，**465.9MB**，iOS 16+，v1.0.5，**2026-09-23 上架**（截至取证仅 3 周），主体广州云知科技 | [cite:7] |
| Android | 小米商店标注 **564MB**，主体广州韫智科技（双主体运营）；官网私域授权分发、8 位机器码离线绑定 | [cite:8] |
| 模型分发 | OCR/NER 随安装包，**无云/分析/广告 SDK**，飞行模式可跑；能力更新只靠发版，无静默下载 | [cite:9] |
| 能力裁剪 | 移动端 **17 类实体**（桌面 45 类），四语 NER + OCR + 印章/条码/二维码/头像视觉检测；无 Excel/批量/还原 | [cite:7] |
| iOS 限制 | 免费 Lite：导出带水印、PDF/Word 仅前 5 页、每日 10 份 | [cite:7] |

### 6.2 截图反推的技术管线

1. **docx 不保留版式**：统一抽成流式文本重排渲染、行内高亮——移动端**没有 Office 回写栈**。
2. **PDF/扫描件走图像路线**：整页栅格化，命中实体画坐标框（原文态黄色半透明、脱敏态色块**烧录进像素**）；印章按圆形、二维码按矩形做视觉检测。
3. **anchor 标签同构**：遮罩块直接印 `【证件号1】【机构4】` 式编号，与我方 `{{PERSON_1}}` 同构——双端共享的是**标签/编号体系与模型家族**，权重是端侧裁剪版，不是同一个模型包。
4. **手机端复核极简**：点高亮块改类型/取消、框选补脱、悬浮工具条（搜索/缩放/调色板/撤销）；无质量评分。
5. **入口三场景**：本机文件、**微信下载目录直读**、剪贴板；OCR 用前台服务带进度可暂停；底部 4 Tab（工作台/拍照/截图/我的）；扫描含文档/证件/屏幕三模式 + 自动裁边透视校正。

**关键判断：它的移动端本质是「OCR + 坐标遮罩 App」，不是桌面引擎的移植。** 检测层下沉、文档回写栈不上手机——与我方规划的路线一致；我方已有的"命中敏感信息 PDF 页整页栅格化"安全边界即同一技术路线。

### 6.3 未坐实项与验证方法

UI 框架（Flutter/原生/RN）与推理框架（onnxruntime/ncnn/MNN）无法从外部确认：APK 仅私域分发、上架仅 3 周，第三方镜像均未收录。取得 Android 授权包（¥128）后即可 5 分钟判定：

```bash
unzip LawRedact.apk -d lr
ls lr/lib/arm64-v8/          # libflutter.so=Flutter; libhermes/libjsc=RN
ls lr/assets/flutter_assets  # 存在即 Flutter 铁证
# libonnxruntime.so / libncnn / libMNN.so / libexecutorch.so = 推理框架
```

### 6.4 对我方的决策含义

- 移动端仅 LawRedact 一家做，且为赠品/Lite 定位，不构成付费理由，**后置**。
- 若做：走"拍照/扫描/截图快脱"轻量路线（Android 先行、iOS 免费 Lite、Harmony 缓议），与 6.2 管线对齐——OCR 用平台原生（Vision / ML Kit），NER 用 INT8 量化（目标 <300MB）。
- 引擎侧只下沉检测层为双端共享核心（Rust + UniFFI/JNI），桌面 Python 引擎不动；UI 壳倾向 Capacitor 复用 React，**不因竞品可能用 Flutter 而跟 Flutter**（其桌面无跨端复用包袱，我方有 React + Tauri 存量）。定栈前先执行 6.3 验证。

## Sources

- [cite:1] LawRedact 主站：<a href="https://www.lawredact.com/">lawredact.com</a>（2026-10-14 抓取）
- [cite:2] LawRedact 下载页：<a href="https://www.lawredact.com/download">lawredact.com/download</a>（2026-10-14）
- [cite:3] LawRedact 定价页：<a href="https://www.lawredact.com/pricing">lawredact.com/pricing</a>（2026-10-14）
- [cite:4] 零信脱敏官网：<a href="https://localmask.com/">localmask.com</a>（2026-10-14）
- [cite:5] 律隐盾官网：<a href="https://lawsec.bugutech.cn/">lawsec.bugutech.cn</a>（2026-10-14）
- [cite:6] Microsoft Presidio：<a href="https://microsoft.github.io/presidio/anonymizer/index.html">官方文档</a> · <a href="https://pypi.org/project/presidio/">PyPI</a>（2026-10-14）
- [cite:7] LawRedact App Store 中国区元数据（iTunes Search API，bundleId=com.lawredact.app，2026-10-14 查询）：<a href="https://apps.apple.com/cn/app/id6808878808">App Store 页面</a>
- [cite:8] 小米应用商店详情（包名 com.lawredact.app，564MB，2026-10-14 抓取）：<a href="https://app.mi.com/details?id=com.lawredact.app">app.mi.com</a>
- [cite:9] LawRedact Android 隐私政策（生效 2026-06-01，更新 2026-09-07）：<a href="https://www.lawredact.com/legal/privacy-android">privacy-android</a>
- 本项目事实：README.md、packages/docanon-core/src/docanon_core/{cli.py,config.py,server/routes.py}、configs/*.yaml、LICENSE（MIT）
