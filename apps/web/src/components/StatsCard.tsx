type Props = { counts: Record<string, number> };

export function StatsCard({ counts }: Props) {
  const entries = Object.entries(counts);
  return (
    <div className="rounded-xl border bg-card p-3.5">
      <h3 className="mb-2.5 text-[13px] font-semibold tracking-wide text-muted-foreground">命中统计</h3>
      <table id="stats" className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="border-b px-2 py-1.5 font-medium">类型</th>
            <th className="border-b px-2 py-1.5 font-medium">数量</th>
          </tr>
        </thead>
        <tbody>
          {entries.length ? (
            entries.map(([k, v]) => (
              <tr key={k}>
                <td className="border-b px-2 py-1.5">{k}</td>
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
