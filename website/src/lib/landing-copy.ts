/**
 * 落地页文案(中英各一份) —— 组件只有一套(`Landing.tsx`), 文案都在这里。
 *
 * 为什么单独放一个文件: 落地页与文档站是两个入口, 但它们讲的是同一个产品;
 * 文案与组件混在一起时, 加一种语言就得复制一遍组件 —— 那正是"复用靠包不靠复制"要避免的。
 */

export type HeroSegment = { text: string } | { br: true } | { hi: string };

export type LandingCopy = {
  htmlLang: string;
  title: string;
  metaDescription: string;
  nav: { docs: string; architecture: string; github: string; switchLabel: string };
  badge: string;
  hero: HeroSegment[];
  sub: string;
  cta: string;
  featuresTitle: string;
  features: { icon: "languages" | "offline" | "format" | "loud" | "recall" | "resume"; title: string; body: string }[];
  stats: { value: number; suffix: string; label: string }[];
  docsTitle: string;
  docs: { href: string; group: string; title: string; summary: string }[];
  footerLicense: string;
  footerTech: string;
};

export const COPY: Record<"zh" | "en", LandingCopy> = {
  zh: {
    htmlLang: "zh-CN",
    title: "doc-anonymizer · 本地文档脱敏",
    metaDescription: "中文优先、全离线、保留原格式的本地文档脱敏工具",
    nav: { docs: "文档", architecture: "架构", github: "GitHub", switchLabel: "English" },
    badge: "MIT · 本地运行 · 不联网",
    hero: [
      { text: "把中文文档里的敏感信息，" },
      { br: true },
      { text: "在" },
      { hi: "本机" },
      { text: "抹掉" },
    ],
    sub: "人名、手机号、身份证、银行卡、邮箱、IP、统一社会信用代码、密钥、自定义词 —— 识别并替换，输出与原文格式相同的文件，外加一份可还原的对照表。",
    cta: "5 分钟快速上手",
    featuresTitle: "特性",
    features: [
      { icon: "languages", title: "中文优先", body: "规则 + 中文词典 + 两个中文 NER 模型并集，专治中文文档里的姓名与机构。" },
      { icon: "offline", title: "全离线", body: "没有任何云端调用；可选的本地大模型路线也只连本机 llama-server。" },
      { icon: "format", title: "保留原格式", body: "docx 按 run 改写、xlsx/csv 改单元格、pdf/图片涂黑，前后可左右对照。" },
      { icon: "loud", title: "不许静默少一层", body: "引擎起不来就在跑前报错退出，不产出“少了识别”的结果。" },
      { icon: "recall", title: "召回优先", body: "拿不准的一律标出；命中位置与来源在运行日志里逐条可查。" },
      { icon: "resume", title: "可续跑可还原", body: "账本每文件落盘，--resume 不重做；mapping.json 能把文本产物还原回去。" },
    ],
    stats: [
      { value: 4, suffix: "", label: "检测引擎（规则/词典/ONNX NER/LLM）" },
      { value: 34, suffix: "ms", label: "ONNX 路线每例耗时（实测）" },
      { value: 8, suffix: " 种", label: "输入格式（含扫描件与图片）" },
      { value: 0, suffix: "", label: "运行期网络请求" },
    ],
    docsTitle: "文档",
    docs: [
      { href: "/start/quickstart/", group: "开始", title: "快速上手", summary: "5 分钟跑通 + 常见问题" },
      { href: "/start/readme/", group: "开始", title: "使用手册", summary: "命令、产物、配置、引擎与已知限制" },
      { href: "/dev/architecture/", group: "开发", title: "架构与目录设计", summary: "五包结构、硬边界、决策记录" },
      { href: "/dev/contributing/", group: "开发", title: "贡献指南", summary: "环境、测试、提交与 PR" },
      { href: "/dev/agents/", group: "开发", title: "开发契约", summary: "不能违反的边界、命令与坑" },
      { href: "/other/security/", group: "其他", title: "安全策略", summary: "漏脱敏怎么报、设计上的边界" },
    ],
    footerLicense: "MIT © 2026 LawyerCH · 组件来自 velora-ui（MIT）",
    footerTech: "Astro + Starlight · Tailwind CSS 4 · 静态输出",
  },
  en: {
    htmlLang: "en",
    title: "doc-anonymizer · local document redaction",
    metaDescription: "Chinese-first, fully offline redaction for local documents, with the original format preserved",
    nav: { docs: "Docs", architecture: "Architecture", github: "GitHub", switchLabel: "中文" },
    badge: "MIT · Runs locally · No network",
    hero: [
      { text: "Wipe the sensitive data out of Chinese documents — " },
      { br: true },
      { text: "on " },
      { hi: "your own machine" },
    ],
    sub: "Names, phone numbers, ID cards, bank cards, emails, IPs, unified social credit codes, secrets, custom terms — detected and replaced. Output keeps the original file format, plus a mapping table you can restore from.",
    cta: "5-minute quickstart",
    featuresTitle: "What it does",
    features: [
      { icon: "languages", title: "Chinese-first", body: "Rules + a Chinese dictionary + two Chinese NER models, unioned. Built for names and organisations in Chinese documents." },
      { icon: "offline", title: "Fully offline", body: "No cloud calls at all. The optional LLM route only talks to a local llama-server." },
      { icon: "format", title: "Format preserved", body: "docx rewritten run by run, xlsx/csv cell by cell, pdf/images blacked out — with a side-by-side before/after." },
      { icon: "loud", title: "Never silently skip a layer", body: "If an engine cannot start, the run fails before writing anything — instead of producing output with missing detections." },
      { icon: "recall", title: "Recall first", body: "Anything uncertain is flagged; every hit's location and source is listed in the run log." },
      { icon: "resume", title: "Resumable, restorable", body: "The ledger is written per file, so --resume never redoes work; mapping.json restores text outputs." },
    ],
    stats: [
      { value: 4, suffix: "", label: "detection engines (rules / dictionary / ONNX NER / LLM)" },
      { value: 34, suffix: "ms", label: "per example on the ONNX route (measured)" },
      { value: 8, suffix: "", label: "input formats (incl. scans and images)" },
      { value: 0, suffix: "", label: "runtime network requests" },
    ],
    docsTitle: "Documentation",
    docs: [
      { href: "/en/start/quickstart/", group: "Start", title: "Quickstart", summary: "Working in 5 minutes + FAQ" },
      { href: "/en/start/readme/", group: "Start", title: "Manual", summary: "Commands, outputs, config, engines and known limits" },
      { href: "/en/dev/architecture/", group: "Development", title: "Architecture", summary: "Five packages, hard boundaries, decisions" },
      { href: "/en/dev/contributing/", group: "Development", title: "Contributing", summary: "Setup, tests, commits, PRs" },
      { href: "/en/dev/agents/", group: "Development", title: "Dev contract (中文)", summary: "Boundaries that must not be broken — currently Chinese only" },
      { href: "/en/other/security/", group: "Other", title: "Security policy (中文)", summary: "How to report a leak, design boundaries" },
    ],
    footerLicense: "MIT © 2026 LawyerCH · components from velora-ui (MIT)",
    footerTech: "Astro + Starlight · Tailwind CSS 4 · static output",
  },
};
