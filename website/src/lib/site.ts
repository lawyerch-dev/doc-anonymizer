/**
 * 站内链接必须走这里 —— Astro 的 `base` 只影响它自己生成的链接(侧栏/搜索/TOC)；
 * 手写在 .astro/.tsx 里的 `href="/..."` 在子路径部署(如 GitHub Pages 项目页)会 404。
 *
 * `import.meta.env.BASE_URL` 由 vite 注入, 等于 astro.config 的 `base`(默认 "/")。
 */
const RAW_BASE = import.meta.env.BASE_URL || "/";

/** 站点根(无尾斜杠): 子路径部署时形如 "/doc-anonymizer"; 根部署时是 "" */
export const BASE = RAW_BASE.replace(/\/+$/, "");

/** 把站内绝对路径加上 base: url("/start/quickstart/") → "/doc-anonymizer/start/quickstart/" */
export function url(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${BASE}${p}`;
}
