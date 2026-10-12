/**
 * 「上传 / 选文件夹」的收件偏好: 收哪些类型、要不要连子文件夹。
 *
 * 存 localStorage(与 `docanon.theme`/`docanon.config` 同一套做法), **不进后端** —— 它是
 * "这台机器上我想怎么挑文件"的界面偏好, 与脱敏能力、方案无关。
 *
 * 默认两条都是实测反馈定的: 选错一个代码仓库时, 里面成百上千个 `.md`/`.txt`/`.png`
 * (子目录里更多)会被当成待脱敏文档全捞进来。所以默认**只收办公文档 + 只收所选文件夹这一层**。
 */
export type UploadPrefs = {
  /** 收件规则: 收哪些扩展名(带点, 如 ".docx")。**能力清单本身仍由后端 `/api/formats` 给** */
  extensions: string[];
  /** 是否连子文件夹一起收(默认 false: 只收所选文件夹里的文件) */
  recursive: boolean;
};

/** 办公文档: 默认收的那一档 */
export const OFFICE_EXTS = [".doc", ".docx", ".xls", ".xlsx", ".wps", ".pdf", ".csv"];
/** 纯文本: 单列一组, 便于"要不要收 .md/.txt"单独勾 */
const TEXT_EXTS = [".txt", ".md", ".markdown", ".text"];

export const DEFAULT_UPLOAD_PREFS: UploadPrefs = { extensions: [...OFFICE_EXTS], recursive: false };

const KEY = "docanon.upload";

export function loadUploadPrefs(): UploadPrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_UPLOAD_PREFS, extensions: [...DEFAULT_UPLOAD_PREFS.extensions] };
    const parsed = JSON.parse(raw) as Partial<UploadPrefs>;
    return {
      extensions: Array.isArray(parsed.extensions)
        ? parsed.extensions.filter((e): e is string => typeof e === "string")
        : [...DEFAULT_UPLOAD_PREFS.extensions],
      recursive: parsed.recursive === true,
    };
  } catch {
    return { ...DEFAULT_UPLOAD_PREFS, extensions: [...DEFAULT_UPLOAD_PREFS.extensions] };
  }
}

export function saveUploadPrefs(prefs: UploadPrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // 存不下只影响"下次还记得", 不该打断这一批
  }
}

/**
 * 设置里按组勾选。组的划分只在这里定义, **成员一律从后端给的清单里取** ——
 * 将来加个抽取器, 它会自动落进「图片与其它」, 不会在这里漏掉。
 */
export function groupExtensions(
  formats: string[],
): { id: string; label: string; hint: string; exts: string[] }[] {
  const office = formats.filter((e) => OFFICE_EXTS.includes(e));
  const text = formats.filter((e) => TEXT_EXTS.includes(e));
  const rest = formats.filter((e) => !OFFICE_EXTS.includes(e) && !TEXT_EXTS.includes(e));
  return [
    { id: "office", label: "办公文档", hint: "案卷材料通常是这一档", exts: office },
    { id: "text", label: "纯文本", hint: "笔记、日志、Markdown", exts: text },
    { id: "rest", label: "图片与其它", hint: "扫描件走 OCR，会慢一些", exts: rest },
  ].filter((g) => g.exts.length);
}

/** 一句话说清当前收件规则(列表上方与设置面板共用这一处措辞) */
export function uploadRuleSummary(prefs: UploadPrefs, formats: string[]): string {
  const n = prefs.extensions.length;
  const all = formats.length > 0 && formats.every((e) => prefs.extensions.includes(e));
  const officeOnly = OFFICE_EXTS.every((e) => prefs.extensions.includes(e)) && n === OFFICE_EXTS.length;
  const scope = n === 0 ? "什么都没收" : all ? `全部类型（${n} 类）` : officeOnly ? `办公文档（${n} 类）` : `自定义（${n} 类）`;
  return `收件：${scope} · ${prefs.recursive ? "含子文件夹" : "只收这一层"}`;
}
