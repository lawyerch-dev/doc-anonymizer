import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@doc-anonymizer/ui/primitives/accordion";
import { groupExtensions, uploadRuleSummary, type UploadPrefs } from "../lib/uploadPrefs";

type Props = {
  /** 后端给的能力清单(/api/formats): 组与成员都从它推导, 这里不硬编码格式名单 */
  formats: string[];
  prefs: UploadPrefs;
  onChange: (next: UploadPrefs) => void;
  /** 从左边那栏的「改」进来时默认展开; 从顶栏「设置」进来时收起(与另两节一样, 默认不占地方) */
  defaultOpen: boolean;
};

/**
 * 设置里的「上传文件」: 「选择文件夹」收哪些类型、要不要连子文件夹。
 * 与「自定义脱敏」「检测引擎」同一套 Accordion 交互(可折叠), 当前规则直接写在标题行右侧。
 *
 * 默认只收办公文档、只收所选文件夹这一层 —— 实测反馈: 选到代码仓库之类的目录时, 几百个
 * `.md`/图片会被当成待脱敏文档捞进来。
 */
export function UploadPrefsPanel({ formats, prefs, onChange, defaultOpen }: Props) {
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
    <Accordion defaultValue={defaultOpen ? ["upload"] : []}>
      <AccordionItem value="upload">
        <AccordionTrigger
          className="py-3.5 text-base font-semibold hover:no-underline"
          title="「选择文件夹」时收哪些文件、要不要遍历子文件夹。默认只收办公文档、只收所选文件夹这一层。"
        >
          {/* 只放标题: 触发器的宽度是满的, 右侧再塞一行摘要就会与折叠箭头叠在一起 */}
          上传文件
        </AccordionTrigger>
        <AccordionContent className="pb-5">
          <p className="mb-3 text-xs leading-snug text-muted-foreground">
            「选择文件夹」时收哪些文件。默认只收办公文档、只收所选文件夹这一层 ——
            免得选到代码仓库之类的目录，把几百个 .md／图片当成待脱敏文档捞进来。
          </p>

          <div className="space-y-3">
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

          <label className="flex cursor-pointer items-start gap-2.5 pt-3.5 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4 flex-none"
              checked={prefs.recursive}
              onChange={(e) => onChange({ ...prefs, recursive: e.target.checked })}
            />
            <span>
              遍历子文件夹
              <span className="block text-xs font-normal leading-snug text-muted-foreground">
                勾上就连子文件夹里的文件一起收；默认不勾，只收所选文件夹这一层。
              </span>
            </span>
          </label>

          {/* 规则摘要放在展开区里 —— 收起来时左栏那行「收件：…」也一直看得见 */}
          <p className="pt-3.5 text-xs tabular-nums text-muted-foreground">
            当前：{uploadRuleSummary(prefs, formats)}
          </p>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
