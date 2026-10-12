/**
 * 落地页文案(中英各一份) —— 组件只有一套(`Landing.tsx`), 文案都在这里。
 *
 * 为什么单独放一个文件: 落地页与文档站是两个入口, 但它们讲的是同一个产品;
 * 文案与组件混在一起时, 加一种语言就得复制一遍组件 —— 那正是"复用靠包不靠复制"要避免的。
 *
 * 三条写作纪律:
 * 1. **只写实测过的**。每句都得能被 `docanon run` + 打开产物核对验证; 说不准就删, 不要往回找补。
 * 2. **一句只说一件事**。首页读者是法务/人力/财务, 不是工程师 —— 不讲 ONNX/--resume/五包结构,
 *    那些归文档站。
 * 3. **限制与卖点同权重**。不脱敏的地方(页眉页脚、不可还原的产物)照写, 这一页是给要拿它交付的人看的。
 *
 * 版式是"六段 + 编号"结构(骨架参考 ohmyppt.cc, 风格沿用我们自己的主题):
 * Hero → 01 三栏长文 → 02 两列错位能力大卡 → 03 四步 + 谁在用 → 04 文档 → 05 结尾 CTA 卡。
 * 编号写在组件里(中英同一个号), 这里只放各段的标题文案。
 *
 * `mock.src` / `mock.out` 里的 `[[...]]` 是"这一处被认成敏感"的记号, 由 `AppMock.tsx` 解析。
 * 脱敏后那一栏用的是「通用」方案的真实输出(人名机构压成 `**`, 号码打码留首尾), 不是占位符。
 */

export type FeatureIcon =
  | "offline"
  | "format"
  | "loud"
  | "chinese"
  | "legacy"
  | "scan"
  | "batch"
  | "stats";

export type LandingCopy = {
  htmlLang: string;
  title: string;
  metaDescription: string;
  nav: { docs: string; github: string; switchLabel: string };
  /* Hero */
  badge: string;
  h1: string;
  sub: string;
  download: string;
  cta: string;
  downloadHint: string;
  entities: string[];
  stats: { value: number; suffix: string; label: string }[];
  /* 01 三栏长文 */
  introLabel: string;
  introTitle: string;
  intro: { title: string; body: string }[];
  /* 02 能力大卡 */
  featuresLabel: string;
  featuresTitle: string;
  features: { icon: FeatureIcon; title: string; body: string }[];
  /* 03 四步 + 谁在用 */
  howLabel: string;
  stepsTitle: string;
  steps: { title: string; body: string }[];
  scenariosTitle: string;
  scenarios: { audience: string; title: string; body: string }[];
  /* 04 文档 */
  docsLabel: string;
  docsTitle: string;
  docs: { href: string; group: string; title: string; summary: string }[];
  /* 05 结尾 CTA 卡 */
  ctaLabel: string;
  ctaTitle: string;
  ctaSub: string;
  ctaChips: string[];
  ctaButton: string;
  ctaHint: string;
  /* 产品界面示意(纯 DOM, 没有图片资产) */
  mock: {
    alt: string;
    title: string;
    scheme: string;
    run: string;
    files: { name: string; status: string }[];
    srcTitle: string;
    outTitle: string;
    src: string[];
    out: string[];
  };
  footerLinks: { label: string; href: string }[];
  footerLicense: string;
  footerTech: string;
};

export const COPY: Record<"zh" | "en", LandingCopy> = {
  zh: {
    htmlLang: "zh-CN",
    title: "doc-anonymizer · 本地文档脱敏",
    metaDescription: "把 Word、Excel、PDF 里的敏感信息在本机抹掉，只改文字、全程不联网",
    nav: { docs: "文档", github: "GitHub", switchLabel: "English" },
    badge: "完全离线 · 文件不出你的电脑",
    h1: "纯本地运行的脱敏工具",
    sub: "Word、Excel、PDF、扫描件和图片里的姓名、电话、身份证号，在你自己的电脑上换掉：只改文字，排版原样。全程不联网。",
    download: "下载桌面版",
    cta: "看怎么用",
    downloadHint:
      "自带运行环境，不用装 Python。macOS 目前只出 Apple Silicon 版，且未签名未公证：首次打开若提示「无法验证开发者」，在「系统设置 → 隐私与安全性」点「仍要打开」。",
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
      { value: 18, suffix: " 种", label: "能直接处理的文件扩展名（Word / Excel / PDF / 图片…）" },
      { value: 0, suffix: " 次", label: "文件上传或联网请求" },
      { value: 100, suffix: "%", label: "处理全部在你自己的电脑上完成" },
      { value: 4, suffix: " 步", label: "从装好到拿到脱敏件（首次含一次模型准备）" },
    ],
    introLabel: "它解决什么",
    introTitle: "守住三件事：不出电脑、只改文字、中文认得出",
    intro: [
      {
        title: "文件不出这台电脑",
        body: "识别与替换全在本机完成，不发任何网络请求。拔了网线再跑一遍，结果一模一样。",
      },
      {
        title: "只改文字，不动排版",
        body: "一份 docx 的 19 个部件里，18 个字节没变，改的只有正文那一个。表格、样式、公式、图表都还在。",
      },
      {
        title: "中文专门做过",
        body: "中文姓名、机构名、统一社会信用代码，由规则、中文词库和两个中文模型一起判，不是拿英文模型硬套。",
      },
    ],
    featuresLabel: "核心能力",
    featuresTitle: "它会把住哪些关",
    features: [
      { icon: "offline", title: "不上传、不联网", body: "程序不发网络请求。拔掉网线再跑一遍，结果完全一样。" },
      { icon: "format", title: "格式与排版保留", body: "只改写命中的文字：正文排版、表格样式、公式与图表都原样带着走。" },
      { icon: "loud", title: "不假装成功", body: "识别引擎起不来就直接报错停下，不会悄悄给你一份漏了项的脱敏件。" },
      { icon: "chinese", title: "中文姓名与机构认得出", body: "规则、中文词库和两个中文模型一起判，结果取并集 —— 宁多勿漏。" },
      { icon: "legacy", title: "旧版 Office 也收", body: ".doc / .xls / .wps 先自动转换再脱敏；产物格式随之变成 .docx / .xlsx，版式可能被重排。" },
      { icon: "scan", title: "扫描件与图片能抹", body: "PDF 命中页整页转成图片，图片按 OCR 定位涂黑，不留一层还能复制的原文字。" },
      { icon: "batch", title: "一整个文件夹一批跑", body: "按收件规则捞能处理的文档，逐份落盘、逐份标状态，最后给一份批次汇总。" },
      { icon: "stats", title: "抹了多少，看得见", body: "跑完给一张按类型统计的命中表；没抹动的也照实写「未命中」，不报成处理完了。" },
    ],
    howLabel: "怎么用",
    stepsTitle: "四步拿到脱敏文件",
    steps: [
      { title: "装好", body: "macOS 把 dmg 里的应用拖进「应用程序」，Windows 跑安装程序。自带运行环境。" },
      { title: "第一次准备", body: "选一套方案，程序在后台把要用的中文模型下好（通用方案约 780MB，只此一次）。" },
      { title: "上传文件或者文件夹", body: "单个文件或整个文件夹都行；方案默认的「通用」多数情况就够用。" },
      { title: "一键脱敏", body: "脱敏件与对照表落进你指定的目录，右栏两栏对照着看。" },
    ],
    scenariosTitle: "谁在用",
    scenarios: [
      {
        audience: "法务",
        title: "合同与法律文书",
        body: "外发前抹掉客户姓名、身份证号与银行账号，条款和排版不动。",
      },
      {
        audience: "人力",
        title: "简历与员工名单",
        body: "给外包或培训机构之前，抹掉手机号、住址与紧急联系人。",
      },
      {
        audience: "财务",
        title: "报表与审计材料",
        body: "交审计或税务之前，抹掉账号与统一社会信用代码，数字本身留着。",
      },
    ],
    docsLabel: "文档",
    docsTitle: "想看细节，从这里进去",
    docs: [
      { href: "/start/quickstart/", group: "开始", title: "快速上手", summary: "5 分钟跑通 + 常见问题" },
      { href: "/start/readme/", group: "开始", title: "使用手册", summary: "命令、产物、配置与已知限制" },
      { href: "/other/security/", group: "其他", title: "安全与隐私", summary: "数据不出本机，漏脱敏怎么报" },
    ],
    ctaLabel: "开始使用",
    ctaTitle: "手边有一份要外发的文件？",
    ctaSub: "先拿一份不敏感的文档跑一遍，看看排版还在不在。",
    ctaChips: ["自带运行环境", "不联网", "中英界面"],
    ctaButton: "下载桌面版",
    ctaHint: "也可以先看文档站的快速上手，再决定装不装。",
    mock: {
      alt: "产品界面示意：左侧是待处理文件清单，右侧是原文与脱敏后的逐行对照",
      title: "脱敏工作台",
      scheme: "方案：通用",
      run: "一键脱敏",
      files: [
        { name: "劳动合同-示例.docx", status: "已抹 12 处" },
        { name: "尽调报告-示例.pdf", status: "已抹 34 处" },
        { name: "员工名单-示例.xlsx", status: "待处理" },
      ],
      srcTitle: "原文",
      outTitle: "脱敏后",
      src: [
        "甲方：[[上海某某科技有限公司]]",
        "联系人：[[张三]]",
        "电话：[[13800001111]]",
        "身份证：[[310101199004120011]]",
        "签署：2026年3月5日 · 金额 128,000.00 元",
      ],
      out: [
        "甲方：[[**]]",
        "联系人：[[**]]",
        "电话：[[138****1111]]",
        "身份证：[[310101********0011]]",
        "签署：2026年3月5日 · 金额 128,000.00 元",
      ],
    },
    footerLinks: [
      { label: "下载桌面版", href: "https://github.com/lawyerch-dev/doc-anonymizer/releases/latest" },
      { label: "文档", href: "/start/quickstart/" },
      { label: "GitHub", href: "https://github.com/lawyerch-dev/doc-anonymizer" },
      { label: "问题反馈", href: "https://github.com/lawyerch-dev/doc-anonymizer/issues" },
    ],
    footerLicense: "MIT 开源 © 2026 LawyerCH · 组件来自 velora-ui",
    footerTech: "本地运行 · 不上传 · 自带运行环境",
  },
  en: {
    htmlLang: "en",
    title: "doc-anonymizer · local document redaction",
    metaDescription:
      "Redact sensitive data in Word, Excel and PDF files on your own machine — only the text changes, fully offline",
    nav: { docs: "Docs", github: "GitHub", switchLabel: "中文" },
    badge: "Fully offline · Your files never leave your computer",
    h1: "A redaction tool that runs entirely on your machine",
    sub: "Swap out names, phone numbers and ID numbers in Word, Excel, PDF, scans and images on your own computer: only the text changes, the layout stays.",
    download: "Download",
    cta: "See how it works",
    downloadHint:
      "The runtime ships inside the app — no Python needed. macOS builds are Apple Silicon only and are not signed or notarised: on first launch, allow it once under System Settings → Privacy & Security.",
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
      { value: 18, suffix: "", label: "file extensions handled today (Word / Excel / PDF / images…)" },
      { value: 0, suffix: "", label: "uploads or network requests" },
      { value: 100, suffix: "%", label: "processed on your own machine" },
      { value: 4, suffix: "", label: "steps from install to redacted file (first run prepares models once)" },
    ],
    introLabel: "What it solves",
    introTitle: "It holds three things: nothing leaves, only text changes, Chinese works",
    intro: [
      {
        title: "The file never leaves this computer",
        body: "Detection and replacement happen locally — no network requests at all. Unplug it, run it again, same output.",
      },
      {
        title: "Text changes, layout does not",
        body: "Of a docx's 19 package parts, 18 stay byte for byte identical — only the document body is rewritten. Tables, styles, formulas and charts survive.",
      },
      {
        title: "Built for Chinese",
        body: "Chinese names, organisations and credit codes come from rules, a Chinese dictionary and two Chinese models — not an English model forced onto Chinese text.",
      },
    ],
    featuresLabel: "Capabilities",
    featuresTitle: "The gates it holds",
    features: [
      { icon: "offline", title: "No uploads, no network", body: "The app sends no requests. Unplug the connection and run it again — identical output." },
      { icon: "format", title: "Formatting preserved", body: "Only the matched text is rewritten: body layout, table styles, formulas and charts all stay." },
      { icon: "loud", title: "No silent success", body: "If a detection engine cannot start, the run fails loudly instead of handing you output with missing redactions." },
      { icon: "chinese", title: "Chinese names and organisations", body: "Rules, a Chinese dictionary and two Chinese models vote together and the results are unioned — flag more, miss none." },
      { icon: "legacy", title: "Old Office files welcome", body: "Legacy .doc / .xls / .wps files are converted first; output becomes .docx / .xlsx and layout may reflow." },
      { icon: "scan", title: "Scans and images too", body: "PDF pages with hits are rendered as whole images; images are painted over at OCR positions — no copyable text layer left." },
      { icon: "batch", title: "Whole folders at once", body: "It takes the documents it can handle, writes them one by one with a status each, then summarises the batch." },
      { icon: "stats", title: "You see what it removed", body: "A per-type hit table after every run; nothing removed is reported as “no hits”, not as done." },
    ],
    howLabel: "How it works",
    stepsTitle: "Four steps to a redacted file",
    steps: [
      { title: "Install", body: "Drag the app out of the dmg on macOS, run the installer on Windows. The runtime comes with it." },
      { title: "Prepare once", body: "Pick a scheme and the Chinese models it needs download in the background (about 780MB for the default, one time)." },
      { title: "Upload files or folders", body: "A single file or a whole folder; the default scheme covers most cases." },
      { title: "One click", body: "The redacted file and its mapping table land in the folder you chose, with a two-pane comparison." },
    ],
    scenariosTitle: "Who uses it",
    scenarios: [
      {
        audience: "Legal",
        title: "Contracts",
        body: "Before it goes out: client names, ID numbers and bank accounts removed, clauses and layout untouched.",
      },
      {
        audience: "HR",
        title: "Résumés and rosters",
        body: "Before an agency sees them: phone numbers, addresses and emergency contacts removed.",
      },
      {
        audience: "Finance",
        title: "Reports and audit packs",
        body: "Before auditors or tax: account numbers and credit codes removed, the figures themselves left alone.",
      },
    ],
    docsLabel: "Documentation",
    docsTitle: "Want the details? Start here",
    docs: [
      { href: "/en/start/quickstart/", group: "Start", title: "Quickstart", summary: "Working in 5 minutes + FAQ" },
      { href: "/en/start/readme/", group: "Start", title: "Manual", summary: "Commands, outputs, config and known limits" },
      { href: "/en/other/security/", group: "Other", title: "Security & privacy", summary: "Nothing leaves your machine; how to report a leak" },
    ],
    ctaLabel: "Get started",
    ctaTitle: "Got a file that needs sending out?",
    ctaSub: "Run one non-sensitive document first and check whether the layout survived.",
    ctaChips: ["Runtime included", "No network", "Chinese & English UI"],
    ctaButton: "Download",
    ctaHint: "Or read the quickstart in the docs first and decide afterwards.",
    mock: {
      alt: "Product interface illustration: a file list on the left, original and redacted text side by side on the right",
      title: "Redaction workspace",
      scheme: "Scheme: general",
      run: "Redact",
      files: [
        { name: "employment-contract-sample.docx", status: "12 spots redacted" },
        { name: "due-diligence-report.pdf", status: "34 spots redacted" },
        { name: "staff-roster-sample.xlsx", status: "pending" },
      ],
      srcTitle: "Original",
      outTitle: "Redacted",
      src: [
        "Party A: [[Shanghai Example Co.]]",
        "Contact: [[Zhang San]]",
        "Tel: [[13800001111]]",
        "ID: [[310101199004120011]]",
        "Signed: 2026-03-05 · Amount 128,000.00 CNY",
      ],
      out: [
        "Party A: [[**]]",
        "Contact: [[**]]",
        "Tel: [[138****1111]]",
        "ID: [[310101********0011]]",
        "Signed: 2026-03-05 · Amount 128,000.00 CNY",
      ],
    },
    footerLinks: [
      { label: "Download", href: "https://github.com/lawyerch-dev/doc-anonymizer/releases/latest" },
      { label: "Docs", href: "/en/start/quickstart/" },
      { label: "GitHub", href: "https://github.com/lawyerch-dev/doc-anonymizer" },
      { label: "Issues", href: "https://github.com/lawyerch-dev/doc-anonymizer/issues" },
    ],
    footerLicense: "MIT © 2026 LawyerCH · components from velora-ui",
    footerTech: "Local-only · No uploads · Runtime included",
  },
};
