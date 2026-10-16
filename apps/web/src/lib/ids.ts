/**
 * 一个短随机 id。界面自己生成 job id / 批次 id 用 —— 只当"这一趟"的把手, 不带任何鉴权含义,
 * 够随机、不撞上就行。之前三处各写一遍拼法, 改格式要动三处。
 */
export function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
