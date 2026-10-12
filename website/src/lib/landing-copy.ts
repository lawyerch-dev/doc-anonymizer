/**
 * 落地页文案(中英各一份) —— 组件只有一套(`Landing.tsx`), 文案都在这里。
 *
 * 为什么单独放一个文件: 落地页与文档站是两个入口, 但它们讲的是同一个产品;
 * 文案与组件混在一起时, 加一种语言就得复制一遍组件 —— 那正是"复用靠包不靠复制"要避免的。
 *
 * 语气约定(别退回工程腔): 首页读者是法务/人力/财务这类普通办公用户 ——
 * 讲"文件会不会传出去""格式还在不在""拿不准会不会漏", 不讲 ONNX/--resume/五包结构。
 * 引擎与命令行那类内容不上首页, 归文档站。
 */

export type ValueIcon = "chinese" | "legacy" | "recall";
export type TrustIcon = "offline" | "format" | "restore" | "loud";

export type LandingCopy = {
  htmlLang: string;
  title: string;
  metaDescription: string;
  nav: { docs: string; github: string; switchLabel: string };
  badge: string;
  h1: string;
  sub: string;
  download: string;
  cta: string;
  downloadHint: string;
  entities: string[];
  stats: { value: number; suffix: string; label: string }[];
  scenariosTitle: string;
  scenarios: { audience: string; title: string; body: string }[];
  stepsTitle: string;
  steps: { title: string; body: string }[];
  trustTitle: string;
  trust: { icon: TrustIcon; title: string; body: string }[];
  valueTitle: string;
  values: { icon: ValueIcon; title: string; body: string }[];
  docsTitle: string;
  docs: { href: string; group: string; title: string; summary: string }[];
  footerLicense: string;
  footerTech: string;
};

export const COPY: Record<"zh" | "en", LandingCopy> = {
  zh: {
    htmlLang: "zh-CN",
    title: "doc-anonymizer · 本地文档脱敏",
    metaDescription: "把 Word、Excel、PDF 里的敏感信息在本机抹掉，格式不变、可还原、全程不联网",
    nav: { docs: "文档", github: "GitHub", switchLabel: "English" },
    badge: "完全离线 · 文件不出你的电脑",
    h1: "纯本地运行的脱敏工具",
    sub: "把 Word、Excel、PDF、扫描件和图片里的姓名、电话、身份证号换掉：排版与格式原样保留，需要时还能还原。全程不联网、不上传。",
    download: "下载桌面版",
    cta: "3 步学会用",
    downloadHint:
      "免安装，下载后直接打开。macOS 首次若提示「无法验证开发者」，在「系统设置 → 隐私与安全性」点「仍要打开」即可。",
    entities: [
      "姓名",
      "手机号",
      "身份证号",
      "银行卡",
      "邮箱",
      "家庭住址",
      "单位名称",
      "车牌",
      "护照",
      "统一社会信用代码",
      "密钥",
      "自定义词",
    ],
    stats: [
      { value: 8, suffix: " 种", label: "支持的文件格式（Word / Excel / PDF / 图片…）" },
      { value: 0, suffix: " 次", label: "文件上传或联网请求" },
      { value: 100, suffix: "%", label: "处理全部在你自己的电脑上完成" },
      { value: 3, suffix: " 步", label: "从下载到拿到脱敏件" },
    ],
    scenariosTitle: "谁在用",
    scenarios: [
      {
        audience: "法务",
        title: "合同与法律文书",
        body: "发给对方或外部律师之前，隐去客户姓名、身份证号与银行账号；条款和格式原样不动。",
      },
      {
        audience: "人力",
        title: "简历与员工名单",
        body: "做背景调查、发给外包或培训机构之前，隐去手机号、住址与紧急联系人。",
      },
      {
        audience: "财务",
        title: "报表与审计材料",
        body: "交给供应商、审计或税务的表格，隐去账号与统一社会信用代码，数字本身保持原样。",
      },
    ],
    stepsTitle: "三步拿到脱敏文件",
    steps: [
      {
        title: "下载打开",
        body: "从 Releases 下载，双击打开即可。不需要装 Python，也不用敲命令。",
      },
      {
        title: "拖进文件",
        body: "把 Word、Excel、PDF 或图片拖进窗口，选一套方案 —— 默认的「通用」多数情况就够用。",
      },
      {
        title: "一键脱敏",
        body: "点「一键脱敏」，脱敏件与对照表落进你指定的目录，两栏可以逐处对照。",
      },
    ],
    trustTitle: "为什么可以放心用",
    trust: [
      { icon: "offline", title: "不上传", body: "程序不联网。你可以拔掉网线再跑一遍，结果完全一样。" },
      { icon: "format", title: "格式不变", body: "Word 还是 Word，Excel 还是 Excel：排版、页眉页脚、表格样式都保留。" },
      { icon: "restore", title: "能还原", body: "每次都会留一份对照表，需要时可以把文本产物还原成原文。" },
      { icon: "loud", title: "不假装成功", body: "识别引擎起不来就直接报错停下，而不是悄悄给你一份漏了项的脱敏件。" },
    ],
    valueTitle: "中文文档专门做过的事",
    values: [
      {
        icon: "chinese",
        title: "中文姓名与机构认得出",
        body: "规则、中文词库和两个中文模型一起判断，不是拿英文模型硬套中文。",
      },
      {
        icon: "legacy",
        title: "旧版 Office 也收",
        body: "旧版 .doc / .xls / .wps 会先自动转换再脱敏；产物格式随之改变，账本里会标明。",
      },
      {
        icon: "recall",
        title: "拿不准的宁可多标",
        body: "每处标注都能逐条查看。宁可多标一处让你核对，也不悄悄漏掉一处。",
      },
    ],
    docsTitle: "文档",
    docs: [
      { href: "/start/quickstart/", group: "开始", title: "快速上手", summary: "5 分钟跑通 + 常见问题" },
      { href: "/start/readme/", group: "开始", title: "使用手册", summary: "命令、产物、配置与已知限制" },
      { href: "/other/security/", group: "其他", title: "安全与隐私", summary: "数据不出本机，漏脱敏怎么报" },
    ],
    footerLicense: "MIT 开源 © 2026 LawyerCH · 组件来自 velora-ui",
    footerTech: "本地运行 · 不上传 · 免安装",
  },
  en: {
    htmlLang: "en",
    title: "doc-anonymizer · local document redaction",
    metaDescription:
      "Redact sensitive data in Word, Excel and PDF files on your own machine — format preserved, restorable, fully offline",
    nav: { docs: "Docs", github: "GitHub", switchLabel: "中文" },
    badge: "Fully offline · Your files never leave your computer",
    h1: "A redaction tool that runs entirely on your machine",
    sub: "Swap out names, phone numbers and ID numbers in Word, Excel, PDF, scans and images: every bit of layout is kept, and you can restore the original later. No network, no uploads.",
    download: "Download",
    cta: "How it works",
    downloadHint:
      "No installer needed — just open it. On macOS the first launch may warn about an unidentified developer; allow it once under System Settings → Privacy & Security.",
    entities: [
      "Names",
      "Phone numbers",
      "ID numbers",
      "Bank cards",
      "Emails",
      "Addresses",
      "Organisations",
      "Plates",
      "Passports",
      "Credit codes",
      "Secrets",
      "Custom terms",
    ],
    stats: [
      { value: 8, suffix: "", label: "file formats (Word / Excel / PDF / images…)" },
      { value: 0, suffix: "", label: "uploads or network requests" },
      { value: 100, suffix: "%", label: "processed on your own machine" },
      { value: 3, suffix: "", label: "steps from download to redacted file" },
    ],
    scenariosTitle: "Who uses it",
    scenarios: [
      {
        audience: "Legal",
        title: "Contracts",
        body: "Before it goes to the other side or outside counsel: hide client names, ID numbers and bank accounts. Clauses and formatting stay untouched.",
      },
      {
        audience: "HR",
        title: "Résumés and rosters",
        body: "Before a background check or sending files to an agency: hide phone numbers, addresses and emergency contacts.",
      },
      {
        audience: "Finance",
        title: "Reports and audit packs",
        body: "For suppliers, auditors or tax filings: hide account numbers and credit codes, leave the figures themselves alone.",
      },
    ],
    stepsTitle: "Redacted files in three steps",
    steps: [
      { title: "Download and open", body: "Grab it from Releases and double-click. No Python, no command line." },
      { title: "Drop your files in", body: "Drop Word, Excel, PDF or image files into the window and pick a scheme — the default handles most cases." },
      { title: "One click", body: "Hit redact. The redacted file and its mapping table land in the folder you chose, side by side with the original." },
    ],
    trustTitle: "Why it is safe to use",
    trust: [
      { icon: "offline", title: "Never uploaded", body: "The app does not use the network. Unplug your connection, run it again — the result is identical." },
      { icon: "format", title: "Format preserved", body: "Word stays Word, Excel stays Excel: layout, headers, footers and table styles are kept." },
      { icon: "restore", title: "Restorable", body: "Every run leaves a mapping table, so text output can be turned back into the original." },
      { icon: "loud", title: "No silent success", body: "If a detection engine cannot start, the run fails loudly instead of handing you output with missing redactions." },
    ],
    valueTitle: "Built for Chinese documents",
    values: [
      { icon: "chinese", title: "Chinese names and organisations", body: "Rules, a Chinese dictionary and two Chinese models vote together — not an English model forced onto Chinese text." },
      { icon: "legacy", title: "Old Office files welcome", body: "Legacy .doc / .xls / .wps files are converted automatically before redaction; the output format changes and the ledger says so." },
      { icon: "recall", title: "Flag rather than miss", body: "Every hit is listed so you can check it. Better to flag one extra spot than to quietly miss one." },
    ],
    docsTitle: "Documentation",
    docs: [
      { href: "/en/start/quickstart/", group: "Start", title: "Quickstart", summary: "Working in 5 minutes + FAQ" },
      { href: "/en/start/readme/", group: "Start", title: "Manual", summary: "Commands, outputs, config and known limits" },
      { href: "/en/other/security/", group: "Other", title: "Security & privacy", summary: "Nothing leaves your machine; how to report a leak" },
    ],
    footerLicense: "MIT © 2026 LawyerCH · components from velora-ui",
    footerTech: "Local-only · No uploads · No installer",
  },
};
