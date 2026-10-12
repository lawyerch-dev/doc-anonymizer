import { Label } from "@doc-anonymizer/ui/primitives/label";
import { groupExtensions, uploadRuleSummary, type UploadPrefs } from "../lib/uploadPrefs";

type Props = {
  /** 后端给的能力清单(/api/formats): 组与成员都从它推导, 这里不硬编码格式名单 */
  formats: string[];
  prefs: UploadPrefs;
  onChange: (next: UploadPrefs) => void;
};

/**
 * 设置里的「上传文件」: 「选择文件夹」收哪些类型、要不要连子文件夹。
 *
 * 默认只收办公文档、只收所选文件夹这一层 —— 实测反馈: 选到代码仓库之类的目录时, 几百个
 * `.md`/图片会被当成待脱敏文档捞进来。
 */
export function UploadPrefsPanel({ formats, prefs, onChange }: Props) {
  const groups = groupExtensions(formats);
  const has = (ext: string) => prefs.extensions.includes(ext);
  const setExts = (exts: string[], on: boolean) => {
    const next = new Set(prefs.extensions);
    for (const e of exts) (on ? next.add(e) : next.delete(e));
    // 按后端给的顺序排, 存下来的值稳定可比(也免得"全选"前后顺序不一样)
    const ordered = formats.length ? formats.filter((f) => next.has(f)) : [...next];
    onChange({ ...prefs, extensions: ordered });
  };

  return (
    <section className="space-y-2.5">
      <Label className="block text-[13px] font-medium">上传文件</Label>
      <p className="text-xs leading-snug text-muted-foreground">
        「选择文件夹」时收哪些文件。默认只收办公文档、只收所选文件夹这一层 ——
        免得选到代码仓库之类的目录，把几百个 .md／图片当成待脱敏文档捞进来。
      </p>

      <div className="space-y-3 pt-1">
        {groups.map((g) => (
          <div key={g.id} className="space-y-1.5">
            <label className="flex cursor-pointer items-center gap-2.5 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={g.exts.every(has)}
                onChange={(e) => setExts(g.exts, e.target.checked)}
              />
              <span className="font-medium">{g.label}</span>
              <span className="text-xs font-normal text-muted-foreground">{g.hint}</span>
            </label>
            <div className="flex flex-wrap gap-x-3.5 gap-y-1 pl-7">
              {g.exts.map((ext) => (
                <label
                  key={ext}
                  className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground"
                >
                  <input
                    type="checkbox"
                    className="size-3.5"
                    checked={has(ext)}
                    onChange={(e) => setExts([ext], e.target.checked)}
                  />
                  {ext}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <label className="flex cursor-pointer items-start gap-2.5 pt-1 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 size-4 flex-none"
          checked={prefs.recursive}
          onChange={(e) => onChange({ ...prefs, recursive: e.target.checked })}
        />
        <span>
          连子文件夹一起收
          <span className="block text-xs font-normal leading-snug text-muted-foreground">
            默认不勾：只收所选文件夹里的文件，子文件夹里的不算。
          </span>
        </span>
      </label>

      <p className="pt-1 text-xs tabular-nums text-muted-foreground">当前：{uploadRuleSummary(prefs, formats)}</p>
    </section>
  );
}
