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
