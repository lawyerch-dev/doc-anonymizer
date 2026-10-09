import { entityLabel } from "../lib/formats";

type Props = {
  counts: Record<string, number>;
  /** 命中合计(与逐类计数同源, 由调用方算好) */
  total: number;
  totalMs: number | null;
  /** 旧版 Office 被自动转换过: 产物格式与版式可能变了, 必须说出来 */
  convertedFrom: string | null;
};

export function StatsCard({ counts, total, totalMs, convertedFrom }: Props) {
  const entries = Object.entries(counts);
  return (
    <div className="rounded-xl border bg-card p-3.5">
      <div className="mb-2.5 flex items-baseline justify-between gap-2">
        <h3 className="text-[13px] font-semibold tracking-wide text-muted-foreground">命中统计</h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          合计 {total}
          {totalMs != null ? ` · ${Math.round(totalMs)}ms` : ""}
        </span>
      </div>
      {convertedFrom ? (
        <p className="mb-2 text-xs text-destructive">
          已由 {convertedFrom} 转换，版式可能被重排
        </p>
      ) : null}
      <table id="stats" className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th scope="col" className="border-b px-2 py-1.5 font-medium">类型</th>
            <th scope="col" className="border-b px-2 py-1.5 font-medium">数量</th>
          </tr>
        </thead>
        <tbody>
          {entries.length ? (
            entries.map(([k, v]) => (
              <tr key={k}>
                <td className="border-b px-2 py-1.5" title={k}>{entityLabel(k)}</td>
                <td className="border-b px-2 py-1.5 tabular-nums">{v}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={2} className="px-2 py-1.5 text-muted-foreground">未命中</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
