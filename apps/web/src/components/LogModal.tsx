import type { ReactNode, RefObject } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@doc-anonymizer/ui/primitives/dialog";
import { entityLabel, locText } from "../lib/formats";
import type { Trace } from "../types";

type Props = {
  open: boolean;
  trace: Trace | null;
  onClose: () => void;
  /** 关掉后焦点回到哪: 显式给, 不指望"上次聚焦的元素" */
  returnFocusTo?: RefObject<HTMLElement | null>;
};

/** 等宽灰底的小标签: 与设置抽屉用同一套 token, 明暗两态都跟着走 */
function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1.5 py-px font-mono text-[12px]">{children}</code>
  );
}

/** 「名称 + 值」: 日志是给用户核对的, 只给值不给名称等于让人猜 */
function Field({ name, value }: { name: string; value: string }) {
  return (
    <span className="inline-flex items-baseline gap-1 whitespace-nowrap">
      <span className="text-muted-foreground">{name}</span>
      <Code>{value}</Code>
    </span>
  );
}

/**
 * 逐条命中溯源。骨架用共享组件库的 Dialog(与设置抽屉的 Sheet 同一套 token 与动效),
 * 焦点陷阱 / Esc 由组件库负责; 关闭后的焦点回收显式交给 `returnFocusTo` —— app 里不再搓第二份弹窗骨架。
 */
export function LogModal({ open, trace, onClose, returnFocusTo }: Props) {
  const t = trace?.timing ?? {};
  const kept = (trace?.detections ?? []).filter((d) => d.strategy === "keep");
  const keptCounts: Record<string, number> = {};
  for (const d of kept) keptCounts[d.entity_type] = (keptCounts[d.entity_type] ?? 0) + 1;

  return (
    <Dialog open={open && trace != null} onOpenChange={(next) => { if (!next) onClose(); }}>
      {trace ? (
        // 高度固定: 日志是一张随时变长的表, 高度不固定的话换文件时会跳一下
        <DialogContent
          className="h-[86vh] w-[min(1150px,92vw)] max-w-none! gap-0"
          finalFocus={returnFocusTo}
        >
          <DialogHeader className="border-b pr-12">
            <DialogTitle>运行日志</DialogTitle>
            <DialogDescription>
              逐条命中溯源：哪个检测器认出、命中什么、替换成了什么。
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-auto overscroll-contain p-4 text-[13px]">
            <div className="mb-3 space-y-1 rounded-lg border bg-muted/40 px-3 py-2.5 text-xs leading-relaxed">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Field name="源文件" value={trace.source} />
                <Field name="抽取器" value={trace.extractor || "-"} />
                {trace.config ? <Field name="口径" value={trace.config} /> : null}
                <Field name="检测器" value={(trace.detectors ?? []).join(" + ") || "-"} />
              </div>
              <div className="text-muted-foreground">
                耗时 抽取 {t.extract_ms ?? "-"}ms · 检测 {t.detect_ms ?? "-"}ms · 回写{" "}
                {t.write_ms ?? "-"}ms · 合计{" "}
                <b className="tabular-nums text-foreground">{t.total_ms ?? "-"}ms</b>
              </div>
              {trace.converted_from ? (
                <div className="text-destructive">
                  已由 {trace.converted_from} 转换，版式可能被重排。
                </div>
              ) : null}
              {kept.length ? (
                <div className="text-muted-foreground">
                  按配置保留 <b className="text-foreground">{kept.length}</b> 处（
                  {Object.entries(keptCounts)
                    .map(([k, v]) => `${entityLabel(k)}×${v}`)
                    .join("、")}
                  ）—— 识别到了，但这几类不在你的脱敏范围。
                </div>
              ) : null}
            </div>

            {trace.detections?.length ? (
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    {["类型", "来源", "策略", "原文", "", "替换为", "位置"].map((h, i) => (
                      <th
                        key={i}
                        className="border-b px-2.5 py-2 font-medium whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trace.detections.map((d, i) => (
                    <tr key={i} className="align-top">
                      <td className="whitespace-nowrap border-b px-2.5 py-2" title={d.entity_type}>
                        {entityLabel(d.entity_type)}
                      </td>
                      <td className="whitespace-nowrap border-b px-2.5 py-2 text-muted-foreground">
                        {d.source}
                      </td>
                      <td className="whitespace-nowrap border-b px-2.5 py-2 text-muted-foreground">
                        {d.strategy}
                      </td>
                      <td className="border-b px-2.5 py-2">
                        <Code>{d.original}</Code>
                      </td>
                      <td className="border-b px-2.5 py-2 text-muted-foreground">→</td>
                      <td className="border-b px-2.5 py-2">
                        <Code>
                          {d.strategy === "keep" ? "（保留原样）" : d.replacement || "（删除）"}
                        </Code>
                      </td>
                      <td className="border-b px-2.5 py-2 text-muted-foreground">
                        {locText(d.locator)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-10 text-center text-muted-foreground">
                本次未命中任何敏感信息。
              </div>
            )}
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
