import type { LandingCopy } from "../lib/landing-copy";

/**
 * 产品界面的**示意**模型 —— 首屏的视觉锚。
 *
 * 为什么不用真截图: 首页要展示的是"拖文件 → 两栏对照 → 一键脱敏"这个形状,
 * 而真截图得往仓库里塞图片资产(中英各一份、样例文档内容会挂上公网)。
 * 这里纯 DOM + Tailwind: 零资产、构建产物不变大、中英共用一套结构。
 *
 * 整块标 `role="img"` + `aria-label`: 它是装饰性的示意, 读屏只念那一句说明,
 * 不会把假文档里的姓名电话当成页面内容逐字读出来。
 */

/** `[[…]]` 包起来的一段 = 被认成敏感信息的那一处 */
function DocLine({ text, tone }: { text: string; tone: "src" | "out" }) {
  const hit =
    tone === "src"
      ? "whitespace-nowrap rounded bg-destructive/15 px-1 text-destructive"
      : "whitespace-nowrap rounded bg-primary/15 px-1 text-primary";
  return (
    <p className="text-xs leading-6">
      {text.split(/(\[\[.*?\]\])/g).map((part, i) =>
        part.startsWith("[[") && part.endsWith("]]") ? (
          <span key={i} className={hit}>
            {part.slice(2, -2)}
          </span>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

export default function AppMock({ mock }: { mock: LandingCopy["mock"] }) {
  return (
    <div
      role="img"
      aria-label={mock.alt}
      className="overflow-hidden rounded-2xl border bg-card text-left shadow-sm"
    >
      <div className="flex items-center gap-3 border-b px-4 py-2.5">
        <span className="flex gap-1.5">
          <span className="size-2.5 rounded-full bg-muted-foreground/30" />
          <span className="size-2.5 rounded-full bg-muted-foreground/30" />
          <span className="size-2.5 rounded-full bg-muted-foreground/30" />
        </span>
        <span className="text-xs font-medium">{mock.title}</span>
      </div>

      <div className="grid sm:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <div className="space-y-2 border-b p-3 sm:border-b-0 sm:border-r">
          {mock.files.map((f) => (
            <div key={f.name} className="rounded-lg border bg-background px-3 py-2">
              <div className="truncate text-xs font-medium">{f.name}</div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">{f.status}</div>
            </div>
          ))}
        </div>

        <div className="grid gap-5 p-4 sm:grid-cols-2">
          {[
            { title: mock.srcTitle, lines: mock.src, tone: "src" as const },
            { title: mock.outTitle, lines: mock.out, tone: "out" as const },
          ].map((pane) => (
            <div key={pane.title}>
              <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                {pane.title}
              </div>
              <div className="space-y-1 rounded-lg border bg-background p-3">
                {pane.lines.map((l) => (
                  <DocLine key={l} text={l} tone={pane.tone} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
        <span className="rounded-md border px-2.5 py-1 text-xs text-muted-foreground">
          {mock.scheme}
        </span>
        <span className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground">
          {mock.run}
        </span>
      </div>
    </div>
  );
}
