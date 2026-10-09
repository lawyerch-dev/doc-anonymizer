export const TEXT_EXT = ["txt", "md", "markdown", "csv"];

export const ENTITY_TYPES = [
  "PHONE", "ID_CARD", "PASSPORT", "PLATE", "BANK_CARD", "EMAIL", "IP", "USCC",
  "PERSON", "ORG", "LOCATION", "AMOUNT", "DOB", "SECRET", "CUSTOM", "DEFAULT",
] as const;

export const STRATEGIES = ["redact", "mask", "placeholder", "pseudonym", "remove", "keep"] as const;

/** 检测器的固定顺序(与后端 detectors 的键一致) */
export const DETECTORS = ["rule", "dictionary", "onnx_ner", "llm_ner"] as const;

/**
 * 检测器 → 给用户看的中文名 + 一句话说明。
 *
 * `rule` / `onnx_ner` 这类名字是代码里的标识, 对用户毫无意义 —— 用户要判断的是
 * "这一层能认出我文档里的什么", 所以名字说"认出什么", 说明说"靠什么认、有什么代价"。
 */
export const DETECTOR_LABELS: Record<string, { name: string; hint: string }> = {
  rule: {
    name: "号码与代码",
    hint: "身份证、手机号、银行卡、邮箱、车牌这类有固定写法的",
  },
  dictionary: {
    name: "我的敏感词",
    hint: "「自定义脱敏」里你填的那些词",
  },
  onnx_ner: {
    name: "中文人名与机构",
    hint: "本机小模型，认人名、机构名、地址；不用联网，快",
  },
  llm_ner: {
    name: "本地大模型",
    hint: "连本机的大模型，能读懂复杂说法；慢一些，要先自己把服务起起来",
  },
};

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
 * L1 下拉的展示顺序 —— 把「推荐（默认）」放最前, 用户第一眼看到的就是该用的那套。
 *
 * 只排序不筛选: 没列进这里的(以后新增的内置、以及"我的配置")按后端给的原顺序排在后面,
 * 一个都不会被藏掉。
 */
export const SCHEME_ORDER = ["onnx.yaml", "legal.yaml", "default.yaml", "llm.yaml"];

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
