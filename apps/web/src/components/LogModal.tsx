import { locText } from "../lib/formats";
import type { Trace } from "../types";

type Props = { open: boolean; trace: Trace | null; onClose: () => void };

export function LogModal({ open, trace, onClose }: Props) {
  if (!open || !trace) return null;
  const t = trace.timing ?? {};
  const kept = (trace.detections ?? []).filter((d) => d.strategy === "keep");
  const keptCounts: Record<string, number> = {};
  for (const d of kept) keptCounts[d.entity_type] = (keptCounts[d.entity_type] ?? 0) + 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex h-4/5 w-3/4 flex-col overflow-hidden rounded-xl bg-slate-900 text-slate-200 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-3 text-sm">
          <b>运行日志</b>
          <button className="text-xs text-slate-300 hover:text-white" onClick={onClose}>关闭 ✕</button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-3 text-xs leading-relaxed">
          <div className="mb-2 text-slate-400">
            源文件 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.source}</code> · 抽取器{" "}
            <code className="rounded bg-slate-800 px-1.5 py-px">{trace.extractor}</code>
            {trace.converted_from ? (
              <> · 已由 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.converted_from}</code> 转换(版式可能被重排)</>
            ) : null}
            {trace.config ? (
              <> · 口径 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.config}</code></>
            ) : null}
            {" · "}检测器 <code className="rounded bg-slate-800 px-1.5 py-px">{(trace.detectors ?? []).join(" + ")}</code>
            <br />
            耗时: 抽取 {t.extract_ms ?? "-"}ms · 检测 {t.detect_ms ?? "-"}ms · 回写 {t.write_ms ?? "-"}ms · 合计{" "}
            <b>{t.total_ms ?? "-"}ms</b>
            {kept.length ? (
              <>
                <br />按配置保留 <b>{kept.length}</b> 处（
                {Object.entries(keptCounts).map(([k, v]) => `${k}×${v}`).join("、")}）
                —— 识别到了，但这几类不在你的脱敏范围
              </>
            ) : null}
          </div>
          {trace.detections?.length ? (
            <table className="w-full border-collapse">
              <thead>
                <tr className="text-left text-slate-400">
                  {["类型", "来源", "策略", "原文", "", "替换为", "位置"].map((h, i) => (
                    <th key={i} className="border-b border-slate-700 px-2 py-1.5 font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trace.detections.map((d, i) => (
                  <tr key={i} className="align-top">
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.entity_type}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.source}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.strategy}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">
                      <code className="rounded bg-slate-800 px-1.5 py-px">{d.original}</code>
                    </td>
                    <td className="border-b border-slate-700 px-2 py-1.5 text-slate-500">→</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">
                      <code className="rounded bg-slate-800 px-1.5 py-px">
                        {d.strategy === "keep" ? "（保留原样）" : (d.replacement || "（删除）")}
                      </code>
                    </td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{locText(d.locator)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-slate-400">本次未命中任何敏感信息。</div>
          )}
        </div>
      </div>
    </div>
  );
}
