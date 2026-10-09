export const TEXT_EXT = ["txt", "md", "markdown", "csv"];

export const ENTITY_TYPES = [
  "PHONE", "ID_CARD", "PASSPORT", "PLATE", "BANK_CARD", "EMAIL", "IP", "USCC",
  "PERSON", "ORG", "LOCATION", "AMOUNT", "DOB", "SECRET", "CUSTOM", "DEFAULT",
] as const;

export const STRATEGIES = ["redact", "mask", "placeholder", "pseudonym", "remove", "keep"] as const;

/**
 * "要不要用模型来认" —— L3 唯一的那道选择题。
 *
 * 底下确实是 4 个检测器(core 的 `detectors`), 但把它们平铺成 4 个勾选框是错的: 里面混了两件事 ——
 * 「规则/词典」是**确定性识别**(写死的格式 + 你填的词表), 「ONNX/LLM」才是**模型识别**, 而且后两者
 * 认的东西高度重叠。所以旧版看起来像"4 个并列的类别", 用户自然会问"为啥混在一起"。
 *
 * 另外, 规则与词典**不该给开关**: 关掉它们只会静默漏检, 而"不想要某类信息"有正确的表达方式 ——
 * 在「自定义脱敏」里把那一类的策略设成 `keep`(保持原样)。词表为空 = 词典等于没开。
 */
export type RecognitionMode = "none" | "onnx" | "llm" | "both";

export const RECOGNITION_MODES: { id: RecognitionMode; name: string; hint: string }[] = [
  {
    id: "none",
    name: "不用模型",
    hint: "只认固定写法的号码、邮箱这类，和你自己填的词表；最快，不用下载任何模型",
  },
  {
    id: "onnx",
    name: "本机小模型",
    hint: "认得人名、机构、地址；不联网，毫秒级",
  },
  {
    id: "llm",
    name: "本地大模型",
    hint: "认得更全，能看懂复杂说法；慢（秒级），服务由 app 自动起",
  },
  {
    id: "both",
    name: "小模型 + 大模型都用",
    hint: "两边的结果取并集，覆盖最全，也最慢",
  },
];

/** 当前配置落在哪一档; 模型都没开就是"不用模型" */
export function recognitionMode(detectors: Record<string, boolean>): RecognitionMode {
  const onnx = Boolean(detectors.onnx_ner);
  const llm = Boolean(detectors.llm_ner);
  if (onnx && llm) return "both";
  if (onnx) return "onnx";
  if (llm) return "llm";
  return "none";
}

/**
 * 档位 → detectors。规则与词表**始终开着**: 它们是确定性识别, 关掉只是静默漏检,
 * "不要某类"请把策略设成 `keep`。
 */
export function detectorsFor(mode: RecognitionMode): Record<string, boolean> {
  return {
    rule: true,
    dictionary: true,
    onnx_ner: mode === "onnx" || mode === "both",
    llm_ner: mode === "llm" || mode === "both",
  };
}

/** 策略代码 → 中文名(下拉里显示中文, 提交的仍是代码) */
export const STRATEGY_LABELS: Record<string, string> = {
  redact: "盖成 **",
  mask: "部分打码",
  placeholder: "换成占位符",
  pseudonym: "换成假名",
  remove: "直接删除",
  keep: "保持原样",
};

/**
 * ONNX 模型目录 → 给用户看的名字与"它认什么"。
 *
 * 按**目录名**索引(不按完整路径): 模型目录可由 `onnx.model_dirs` 或下载脚本改名/新增,
 * 完整路径是用户机器上的位置、不是身份。认不出的目录回退到显示目录名 —— 与"类型代码认不出
 * 就照原样显示"同一原则, 宁可爱看不猜。
 *
 * 描述来自实测记录, 不编: 各模型认哪些类别见 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP`
 * 与 [docs/benchmarks.md](../../../docs/benchmarks.md) 的选型表。
 */
export const ONNX_MODEL_INFO: Record<string, { name: string; hint: string; recommended: boolean }> = {
  gyr66: {
    name: "通用中文识别",
    hint: "机构名、人名、地址、角色（如审判员）",
    recommended: true,
  },
  "pii-engineer": {
    name: "个人信息识别",
    hint: "人名、手机号、身份证号、地址",
    recommended: true,
  },
};

/** 目录 → 模型备注; 没登记过的目录: 名字就用目录名, 并说清它没有备注 */
export function onnxModelInfo(dir: string): { name: string; hint: string; recommended: boolean } {
  const base = dir.replace(/\/+$/, "").split("/").pop() ?? dir;
  return ONNX_MODEL_INFO[base] ?? { name: base, hint: "自备模型，没有备注", recommended: false };
}

/**
 * 打开界面时 L1 下拉默认停在哪一套(用户自己选过就以 localStorage 记的为准)。
 *
 * 后端启动时用的 `-c` 是另一回事: 那是"引擎预检按哪套来"。界面默认值在这里定, 改动只影响
 * "用户一进来看到/会用哪套"。
 */
export const DEFAULT_SCHEME = "llm.yaml";

/**
 * L1 下拉的展示顺序 —— 默认那一套放最前, 用户第一眼看到的就是该用的那套。
 *
 * 只排序不筛选: 没列进这里的(以后新增的内置、以及"我的配置")按后端给的原顺序排在后面,
 * 一个都不会被藏掉。
 */
export const SCHEME_ORDER = ["llm.yaml", "onnx.yaml", "legal.yaml", "default.yaml"];

export function orderSchemes<T extends { name: string }>(rows: T[]): T[] {
  const rank = (name: string) => {
    const i = SCHEME_ORDER.indexOf(name);
    return i < 0 ? SCHEME_ORDER.length : i;
  };
  return [...rows].sort((a, b) => rank(a.name) - rank(b.name)); // sort 是稳定的: 同档保持原序
}

/** 字节 → 人话("2.78 GB"/"688 MB"), 给下载进度与模型大小用 */
export function humanSize(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  return `${Math.round(bytes / 1024 ** 2)} MB`;
}

/** 每种策略的效果示例(L2 表格里给人看) */
export const EFFECT: Record<string, string> = {
  redact: "**",
  mask: "138****0000",
  placeholder: "<PHONE_1>",
  pseudonym: "林芳",
  remove: "（删除）",
  keep: "（不动）",
};

/**
 * 实体类型代码 → 给用户看的中文名。
 *
 * 清单来自引擎的真实产出, 不是猜的: 规则层 `detectors/rule.py` 的 PATTERNS、
 * 词典层固定给 `CUSTOM`、ONNX 层经 `config.py` 的 `DEFAULT_ONNX_ENTITY_MAP` 映射后的类型
 * (含 gyr66 的 `POSITION`)、以及兜底的 `DEFAULT`。
 *
 * 漏网的照原样显示代码 —— 用户可以在配置里写自己的 `onnx.entity_map`, 那时会冒出什么标签
 * 我们并不知道; 编一个中文名比显示代码更糟。
 */
export const ENTITY_LABELS: Record<string, string> = {
  PHONE: "电话",
  ID_CARD: "身份证",
  PASSPORT: "护照",
  PLATE: "车牌",
  BANK_CARD: "银行卡",
  EMAIL: "邮箱",
  IP: "IP 地址",
  USCC: "统一社会信用代码",
  PERSON: "人名",
  ORG: "机构名",
  LOCATION: "地址",
  POSITION: "角色",
  DOB: "日期",
  AMOUNT: "金额",
  SECRET: "密钥",
  CUSTOM: "自定义词",
  DEFAULT: "其他",
};

/** 类型代码 → 中文名; 没登记过的原样返回代码 */
export function entityLabel(code: string): string {
  return ENTITY_LABELS[code] ?? code;
}

/** 命中位置 → 人话(与旧 app.js 的 locText 一致) */
export function locText(loc: Record<string, unknown> | undefined): string {
  if (!loc) return "";
  if ("line" in loc) return `第${(loc.line as number) + 1}行`;
  if ("page" in loc) return `第${(loc.page as number) + 1}页${loc.bbox ? "(图)" : ""}`;
  if ("sheet" in loc) return `${loc.sheet}!${loc.cell}`;
  if ("row" in loc) return `r${loc.row}c${loc.col}`;
  if ("paragraph" in loc) return `第${(loc.paragraph as number) + 1}段`;
  return JSON.stringify(loc);
}
