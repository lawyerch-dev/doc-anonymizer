export const TEXT_EXT = ["txt", "md", "markdown", "csv"];

export const ENTITY_TYPES = [
  "PHONE", "ID_CARD", "PASSPORT", "PLATE", "BANK_CARD", "EMAIL", "IP", "USCC",
  "PERSON", "ORG", "LOCATION", "AMOUNT", "DOB", "SECRET", "CUSTOM", "DEFAULT",
] as const;

export const STRATEGIES = ["redact", "mask", "placeholder", "pseudonym", "remove", "keep"] as const;

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
