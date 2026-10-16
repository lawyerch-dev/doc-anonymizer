import { extOf } from "./formats";
import type { UploadPrefs } from "./uploadPrefs";

/**
 * 选文件夹时整层跳过的目录(隐藏目录如 `.git`/`.venv` 由"隐藏项"那条规则一起挡掉)。
 * 选到代码仓库/工程目录时, 这些里面是依赖与构建产物, 不是案子材料。
 */
export const BLOCKED_DIRS = new Set([
  "node_modules", "dist", "build", "target", "out", "vendor", "coverage",
  "__pycache__", "site-packages", "bower_components", "Pods", "DerivedData",
]);

export type PickedFile = { file: File; relpath: string };

export type FolderPlan = {
  folder: string;
  /** 能跑的(在收件类型里、不超单文件上限) */
  todo: PickedFile[];
  /** 收件类型里但超单文件上限的(要让人看见是哪几个) */
  tooBig: PickedFile[];
  /** 列表上方那行"跳过了什么"的计数; 没有可说的就是 null */
  notes: string | null;
  /** 落在子文件夹、又没开「遍历子文件夹」的份数(空态文案要用) */
  nestedCount: number;
};

/**
 * 选文件夹 → 这一批要传什么、跳过了什么。**纯函数**(不碰 state/网络), 好读好测。
 *
 * 收件规则可能与后端的能力清单不一致(改过配置/后端升过级): 以两边都认的为准; 清单没拿到就信规则。
 * 实测反馈: 选错一个代码仓库时, 里面成百上千个 `.md`/`.txt`/`.png`(子目录里更多)也是"能读的类型",
 * 会被全捞进来 —— 所以四类不进项都**计数**写出来, 绝不装作没有("静默少一层"那条边界)。
 */
export function planFolder(
  files: File[],
  prefs: UploadPrefs,
  formats: string[],
  maxFileBytes: number,
): FolderPlan {
  const relOf = (f: File) => (f.webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name;
  const folder = (files[0]?.webkitRelativePath || "").split("/")[0] || "文件夹";
  const allowed = new Set(
    formats.length ? prefs.extensions.filter((e) => formats.includes(e)) : prefs.extensions,
  );

  let hidden = 0;
  let nested = 0;
  let blocked = 0;
  const picked: PickedFile[] = [];
  for (const f of files) {
    const relpath = relOf(f);
    const parts = relpath.split("/");
    if (parts.some((p) => p.startsWith("."))) { hidden += 1; continue; }
    if (parts.length > 1 && !prefs.recursive) { nested += 1; continue; }
    if (parts.slice(0, -1).some((p) => BLOCKED_DIRS.has(p))) { blocked += 1; continue; }
    picked.push({ file: f, relpath });
  }

  const keep: PickedFile[] = [];
  const skipped: PickedFile[] = [];
  for (const x of picked) {
    (allowed.has(extOf(x.file.name)) ? keep : skipped).push(x);
  }
  const todo = keep.filter((x) => x.file.size <= maxFileBytes);
  const tooBig = keep.filter((x) => x.file.size > maxFileBytes);

  const byExt = new Map<string, number>();
  for (const x of skipped) {
    const e = extOf(x.file.name) || "无扩展名";
    byExt.set(e, (byExt.get(e) ?? 0) + 1);
  }
  const top = [...byExt.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
  const rest = skipped.length - top.reduce((n, [, c]) => n + c, 0);
  const notes: string[] = [];
  if (nested) notes.push(`子文件夹里 ${nested} 个未收（设置里可打开「遍历子文件夹」）`);
  if (skipped.length) {
    notes.push(
      `已跳过 ${skipped.length} 个非收件类型（${top.map(([e, c]) => `${e} ${c}`).join(" · ")}` +
      `${rest ? ` 等 ${rest} 个` : ""}）`,
    );
  }
  if (blocked) notes.push(`依赖/构建目录 ${blocked} 个`);
  if (hidden) notes.push(`隐藏项 ${hidden} 个`);

  return { folder, todo, tooBig, notes: notes.length ? notes.join(" · ") : null, nestedCount: nested };
}
