/**
 * 「上传 / 选文件夹」的收件偏好: 收哪些类型、要不要连子文件夹。
 *
 * **存在后端**(`/api/settings` → 数据根下的 `var/settings.json`), 不再是浏览器 localStorage ——
 * 打包成 .app 后它是"软件设置"的一部分: 换台机器、清 WebView 数据、以后换 bundle id 都不该丢,
 * 而且能跟方案一起备份(见 `resources.WRITABLE`)。**默认值只有这一处真相**: 后端没存过就是空,
 * 由界面拿这里的默认值。
 *
 * 默认收**办公文档 + 图片**、且**只收所选文件夹这一层**: 案卷材料基本落在这两档里(扫描件是图片),
 * 而"这一层"是实测反馈定的 —— 选错一个代码仓库时, 里面成百上千个 `.md`/`.txt`(子目录里更多)
 * 会被当成待脱敏文档全捞进来。
 */
export type UploadPrefs = {
  /** 收件规则: 收哪些扩展名(带点, 如 ".docx")。**能力清单本身仍由后端 `/api/formats` 给** */
  extensions: string[];
  /** 是否连子文件夹一起收(默认 false: 只收所选文件夹里的文件) */
  recursive: boolean;
};

/** 办公文档: 默认收的第一档 */
export const OFFICE_EXTS = [".doc", ".docx", ".xls", ".xlsx", ".wps", ".pdf", ".csv"];
/** 图片: 默认收的第二档(扫描件走 OCR, 比办公文档慢) */
export const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"];
/** 纯文本: 单列一组, 便于"要不要收 .md/.txt"单独勾(默认**不收**) */
const TEXT_EXTS = [".txt", ".md", ".markdown", ".text"];

export const DEFAULT_UPLOAD_PREFS: UploadPrefs = {
  extensions: [...OFFICE_EXTS, ...IMAGE_EXTS],
  recursive: false,
};

/** 默认值的一份**副本**(别把模块级那个数组交出去: 谁改一下它就全校跟着变) */
export function defaultUploadPrefs(): UploadPrefs {
  return { ...DEFAULT_UPLOAD_PREFS, extensions: [...DEFAULT_UPLOAD_PREFS.extensions] };
}

/**
 * 设置里按组勾选。组的划分只在这里定义, **成员一律从后端给的清单里取** ——
 * 将来加个抽取器, 它会落进对得上的那一组; 都不像就进「其它」(不硬塞进图片那组)。
 */
export function groupExtensions(
  formats: string[],
): { id: string; label: string; hint: string; exts: string[] }[] {
  const pick = (allow: string[]) => formats.filter((e) => allow.includes(e));
  const rest = formats.filter(
    (e) => !OFFICE_EXTS.includes(e) && !TEXT_EXTS.includes(e) && !IMAGE_EXTS.includes(e),
  );
  return [
    { id: "office", label: "办公文档", hint: "案卷材料通常是这一档", exts: pick(OFFICE_EXTS) },
    { id: "image", label: "图片类", hint: "扫描件走 OCR，会慢一些", exts: pick(IMAGE_EXTS) },
    { id: "text", label: "纯文本", hint: "笔记、日志、Markdown", exts: pick(TEXT_EXTS) },
    { id: "rest", label: "其它", hint: "", exts: rest },
  ].filter((g) => g.exts.length);
}

/** 一句话说清当前收件规则(列表上方与设置面板共用这一处措辞) */
export function uploadRuleSummary(prefs: UploadPrefs, formats: string[]): string {
  const n = prefs.extensions.length;
  const all = formats.length > 0 && formats.every((e) => prefs.extensions.includes(e));
  /** 正好就是这一组(一个不多一个不少) */
  const exactly = (exts: string[]) =>
    exts.every((e) => prefs.extensions.includes(e)) && n === exts.length;
  const scope = n === 0
    ? "什么都没收"
    : all ? `全部类型（${n} 类）`
      : exactly(DEFAULT_UPLOAD_PREFS.extensions) ? `办公文档 + 图片（${n} 类）`
        : exactly(OFFICE_EXTS) ? `办公文档（${n} 类）`
          : `自定义（${n} 类）`;
  return `收件：${scope} · ${prefs.recursive ? "含子文件夹" : "只收这一层"}`;
}
