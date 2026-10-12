import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@doc-anonymizer/ui/primitives/accordion";
import { entityLabel } from "../lib/formats";

type Props = {
  counts: Record<string, number>;
  /** 命中合计(与逐类计数同源, 由调用方算好) */
  total: number;
  totalMs: number | null;
  /** 旧版 Office 被自动转换过: 产物格式与版式可能变了, 必须说出来 */
  convertedFrom: string | null;
};

/**
 * 命中统计: 左栏底部那块。默认展开(跑完就该看见抹了多少), 可折叠收起; 表格限高自带滚动 ——
 * 不然类型一多, 卡片会把左栏撑高, 整列和列表各冒一条滚动条(嵌套滚动最乱)。
 * 折叠用共享库的 Accordion, 与设置里的 L2/L3 同一套交互, 不再手搓箭头。
 */
export function StatsCard({ counts, total, totalMs, convertedFrom }: Props) {
  const entries = Object.entries(counts);
  return (
    <div className="flex-none rounded-xl border bg-card p-3.5">
      <Accordion defaultValue={["stats"]}>
        <AccordionItem value="stats" className="border-b-0">
          <AccordionTrigger className="py-0" title="本次脱敏抹掉了哪些类型、各多少处">
            <span className="flex w-full items-baseline gap-2 pr-1">
              <span className="text-[13px] font-semibold tracking-wide text-muted-foreground">命中统计</span>
              <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                合计 {total}
                {totalMs != null ? ` · ${Math.round(totalMs)}ms` : ""}
              </span>
            </span>
          </AccordionTrigger>
          {/* keepMounted: 收起来也把 #stats 留在 DOM 里 —— 它是 E2E 读取的契约钩子,
              不能因为用户点了一下折叠就整个消失(隐藏元素的 textContent 仍可读) */}
          <AccordionContent className="pb-0" keepMounted>
            {convertedFrom ? (
              <p className="mb-2 text-xs text-destructive">
                已由 {convertedFrom} 转换，版式可能被重排
              </p>
            ) : null}
            <div className="max-h-40 overflow-auto overscroll-contain">
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
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
