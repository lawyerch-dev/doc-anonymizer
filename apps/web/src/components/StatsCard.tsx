import { entityLabel } from "../lib/formats";
import type { BatchSummary } from "../types";

type Props = {
  counts: Record<string, number>;
  /** 命中合计(与逐类计数同源, 由调用方算好) */
  total: number;
  totalMs: number | null;
  /** 旧版 Office 被自动转换过: 产物格式与版式可能变了, 必须说出来 */
  convertedFrom: string | null;
  /** 批次才有: 多少份、几份成了、几份没成 —— 有没产出结果的就必须在这儿说出来 */
  summary?: BatchSummary | null;
};

/**
 * 识别统计面板(右栏): 跑完一次脱敏, 抹了多少处、哪些类型、各多少处。
 *
 * 大数字 + 类型网格的排法参考 LawRedact 的统计侧栏: 一眼先看到总量,
 * 再按数量从多到少扫类型。窄屏时整块回到左栏底部(见 App 的断点搬移)。
 *
 * #stats 是 E2E 契约钩子: 一直在 DOM(不再折叠, 就不需要 keepMounted 的那套兜底)。
 */
export function StatsCard({ counts, total, totalMs, convertedFrom, summary }: Props) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return (
    <section className="flex-none rounded-xl border bg-card p-3.5">
      <h3 className="text-[13px] font-semibold tracking-wide text-muted-foreground">识别统计</h3>

      <div className="mt-2 flex items-end gap-2">
        <span className="text-3xl font-semibold leading-none tabular-nums">{total}</span>
        <span className="pb-0.5 text-xs text-muted-foreground">
          处敏感信息 · {entries.length} 种类型
          {totalMs != null ? ` · ${(totalMs / 1000).toFixed(1)}s` : ""}
        </span>
      </div>

      {/* 批次: 先把"多少份、几份没成"说清楚 —— 只报"完成"而藏着未处理的那几份, 就是静默少一层 */}
      {summary ? (
        <p id="batchSummary" className="mt-2 text-xs tabular-nums text-muted-foreground">
          {summary.total} 份：{summary.ok} 已脱敏
          {summary.unsupported ? ` · ${summary.unsupported} 未处理` : ""}
          {summary.error ? (
            <span className="text-destructive">{` · ${summary.error} 失败`}</span>
          ) : null}
        </p>
      ) : null}
      {convertedFrom ? (
        <p className="mt-2 text-xs text-destructive">
          已由 {convertedFrom} 转换，版式可能被重排
        </p>
      ) : null}

      <div
        id="stats"
        className="scroll-thin mt-3 grid max-h-72 grid-cols-2 gap-1.5 overflow-auto overscroll-contain"
      >
        {entries.length ? (
          entries.map(([k, v]) => (
            // title 给认不出的类型代码留个查证入口(界面上显示的是中文名或原代码)
            <div
              key={k}
              title={k}
              className="flex min-w-0 items-center gap-1.5 rounded-lg border bg-background px-2 py-1.5 text-xs"
            >
              <span className="min-w-0 flex-1 truncate">{entityLabel(k)}</span>
              <span className="flex-none font-medium tabular-nums">{v}</span>
            </div>
          ))
        ) : (
          <p className="col-span-2 text-xs text-muted-foreground">未识别到敏感信息</p>
        )}
      </div>
    </section>
  );
}
