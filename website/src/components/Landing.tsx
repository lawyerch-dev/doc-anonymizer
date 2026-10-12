import {
  ArrowRightIcon,
  FileTextIcon,
  FileType2Icon,
  FolderInputIcon,
  LanguagesIcon,
  ListChecksIcon,
  LockIcon,
  ScanLineIcon,
  ShieldCheckIcon,
  WifiOffIcon,
} from "lucide-react";
import { BlurFade } from "@doc-anonymizer/ui/blur-fade";
import { Marquee } from "@doc-anonymizer/ui/marquee";
import { NumberTicker } from "@doc-anonymizer/ui/number-ticker";
import { buttonVariants } from "@doc-anonymizer/ui/primitives/button";
import { AuroraBackground } from "@doc-anonymizer/ui/aurora-background";
import { GridPattern } from "@doc-anonymizer/ui/grid-pattern";
import { RetroGrid } from "@doc-anonymizer/ui/retro-grid";
import { url } from "../lib/site";
import AppMock from "./AppMock";
import { COPY, type FeatureIcon } from "../lib/landing-copy";

const FEATURE_ICONS: Record<FeatureIcon, typeof WifiOffIcon> = {
  offline: WifiOffIcon,
  format: FileTextIcon,
  loud: ShieldCheckIcon,
  chinese: LanguagesIcon,
  legacy: FileType2Icon,
  scan: ScanLineIcon,
  batch: FolderInputIcon,
  stats: ListChecksIcon,
};

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * 每节的开头: 大号编号 + 主色分类名 + 标题, 底下一条分隔线给"节"划界。
 *
 * 编号原来是 `No.01` 那种灰色小字, 在页面上几乎看不见 —— 它是这一版排版的阅读刻度,
 * 看不见就等于没有, 所以把数字放到最大、分类名用主色, 让它先于标题被读到。
 */
function SectionHead({ no, label, title }: { no: number; label: string; title: string }) {
  return (
    <div className="flex items-end gap-5 border-b pb-6">
      <span className="font-mono text-5xl font-semibold leading-[0.8] text-primary/35 sm:text-6xl">
        {pad(no)}
      </span>
      <div>
        <div className="text-xs font-medium uppercase tracking-widest text-primary">{label}</div>
        <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{title}</h2>
      </div>
    </div>
  );
}

/**
 * 产品落地页。中英共用这一个组件 —— 文案在 `src/lib/landing-copy.ts`,
 * 两条路由(`/` 与 `/en/`)只是传不同的 `locale`。
 *
 * 排版骨架(借自 ohmyppt.cc 那种"大标题 + 编号 + 错位大卡"的节奏, 风格用我们自己的主题):
 * Hero(居中大标题 + 一排按钮 + 产品界面示意) → 01 三栏长文 → 02 两列错位能力大卡 →
 * 03 四步 + 谁在用 → 04 文档 → 05 结尾 CTA 卡。引擎、命令行那类内容不上首页 —— 归文档站。
 *
 * 首屏不套 BlurFade: 那个组件在 JS 跑起来之前把内容藏掉, 用在最大的首屏标题上等于给
 * 无 JS / 慢 JS 的访客一个空白页(组件自己的注释也是这么写的)。
 */
export default function Landing({ repo, locale }: { repo: string; locale: "zh" | "en" }) {
  const c = COPY[locale];
  return (
    <main className="mx-auto max-w-6xl px-6">
      {/* 全站背景(固定层): 滚动时一直在, 免得下方页面只剩纯色底显得空。
          三层: 顶部品牌柔光 → 平铺网格(向下渐隐) → 底部透视网格。
          透视网格有两处必须压住, 否则会留下一条横线:
          1) --border: 组件默认拿它当线色, 浅色下几乎是白色, 网格会看不见。
          2) mask: 组件自带 `to-background` 的渐变, 在容器顶边画了一条不透明的 background 色带,
             会把背后的平铺网格与柔光一刀切断 —— 用向下渐显的遮罩把这一层的入场改成软的。 */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(70% 45% at 50% 0%, color-mix(in oklab, var(--brand) 12%, transparent), transparent 70%)",
          }}
        />
        <GridPattern
          width={48}
          height={48}
          style={{
            // 渐隐要拖到视口下方: 透视网格是从视口 1/3 处渐显上来的, 扁平网格若在 55% 就没了,
            // 两层的交界会留下一条横边。让两者在交界处叠加, 才是过渡而不是拼接。
            maskImage: "radial-gradient(ellipse 78% 88% at 50% 0%, #000 14%, transparent 100%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 78% 88% at 50% 0%, #000 14%, transparent 100%)",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 h-2/3"
          style={
            {
              "--border": "color-mix(in oklab, var(--foreground) 22%, transparent)",
              maskImage: "linear-gradient(to bottom, transparent, #000 55%)",
              WebkitMaskImage: "linear-gradient(to bottom, transparent, #000 55%)",
            } as React.CSSProperties
          }
        >
          <RetroGrid angle={65} cellSize={48} opacity={0.9} />
        </div>
      </div>
      {/* Hero */}
      <section className="relative -mx-6 overflow-hidden px-6 pt-20 pb-16 text-center sm:pt-28">
        <AuroraBackground intensity="subtle" />
        <div className="relative">
          <p className="mb-6 inline-flex items-center gap-2 rounded-full border bg-background/60 px-3 py-1 text-xs text-muted-foreground">
            <LockIcon className="size-3.5" /> {c.badge}
          </p>
          <h1 className="mx-auto max-w-4xl text-4xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
            {c.h1}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">{c.sub}</p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            {/* 下载排第一: 访客来看这个工具, 最想做的事就是拿到它; 次按钮一律 outline。 */}
            <a
              href={`${repo}/releases/latest`}
              className={buttonVariants({ size: "lg", className: "h-11 px-6 text-base" })}
            >
              {c.download} <ArrowRightIcon className="size-4" />
            </a>
            <a
              href="#how"
              className={buttonVariants({
                size: "lg",
                variant: "outline",
                className: "h-11 px-6 text-base",
              })}
            >
              {c.cta}
            </a>
          </div>
          {/* 一行说清"装完为什么会拦一下": 不写的话, 用户下载后被系统拦下, 第一反应是这软件坏了 */}
          <p className="mx-auto mt-4 max-w-2xl text-xs text-muted-foreground">{c.downloadHint}</p>
        </div>
      </section>

      {/* 色带在 hero 底部是被硬裁的, 所以留一段纯色空白再放卡片 —— 不然卡片正压在裁切线上, 看着像贴着首屏 */}
      <BlurFade className="mt-16">
        <AppMock mock={c.mock} />
      </BlurFade>

      <BlurFade delay={0.1}>
        <section className="relative mt-8 overflow-hidden rounded-2xl border">
          <div className="border-b py-4">
            <Marquee pauseOnHover className="[--duration:38s]">
              {c.entities.map((t) => (
                <span key={t} className="mx-2 rounded-md border bg-card px-3 py-1 text-sm">
                  {t}
                </span>
              ))}
            </Marquee>
          </div>
          <div className="grid grid-cols-2 gap-6 px-6 py-8 sm:grid-cols-4">
            {c.stats.map((s, i) => (
              <BlurFade key={s.label} delay={0.05 * i}>
                <div>
                  <div className="text-3xl font-semibold sm:text-4xl">
                    <NumberTicker value={s.value} />
                    {s.suffix}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
                </div>
              </BlurFade>
            ))}
          </div>
        </section>
      </BlurFade>

      {/* 01 三栏长文 */}
      <section className="mt-24">
        <SectionHead no={1} label={c.introLabel} title={c.introTitle} />
        <div className="mt-10 grid gap-10 sm:grid-cols-3">
          {c.intro.map((p, i) => (
            <BlurFade key={p.title} delay={0.06 * i}>
              <div className="border-l pl-5">
                <div className="font-mono text-sm text-primary">{pad(i + 1)}</div>
                <h3 className="mt-3 text-lg font-semibold">{p.title}</h3>
                <p className="mt-2 text-sm leading-7 text-muted-foreground">{p.body}</p>
              </div>
            </BlurFade>
          ))}
        </div>
      </section>

      {/* 02 两列错位大卡 */}
      <section className="mt-24">
        <SectionHead no={2} label={c.featuresLabel} title={c.featuresTitle} />
        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          {c.features.map((f, i) => {
            const Icon = FEATURE_ICONS[f.icon];
            // 单数列时最后一张占满整行, 免得右下角留一个空洞
            const last = i === c.features.length - 1 && c.features.length % 2 === 1;
            return (
                <BlurFade
                  key={f.title}
                  delay={0.05 * (i % 2)}
                  className={`${i % 2 ? "sm:mt-10" : ""} ${last ? "sm:col-span-2" : ""}`}
                >
                  <div className="h-full rounded-2xl border bg-card p-8">
                    <div className="flex items-start justify-between">
                      <span className="grid size-11 place-items-center rounded-xl bg-primary/10">
                        <Icon className="size-5 text-primary" />
                      </span>
                      <span className="font-mono text-sm text-muted-foreground">{pad(i + 1)}</span>
                    </div>
                    <h3 className="mt-6 text-xl font-semibold">{f.title}</h3>
                    <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">{f.body}</p>
                  </div>
                </BlurFade>
              );
          })}
        </div>
      </section>

      {/* 03 四步 + 谁在用 */}
      <section id="how" className="mt-24 scroll-mt-8">
        <SectionHead no={3} label={c.howLabel} title={c.stepsTitle} />
        <ol className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {c.steps.map((s, i) => (
            <li key={s.title} className="border-t pt-5">
              <div className="font-mono text-sm text-primary">STEP {pad(i + 1)}</div>
              <h3 className="mt-3 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-7 text-muted-foreground">{s.body}</p>
            </li>
          ))}
        </ol>
        <h3 className="mt-16 text-2xl font-semibold">{c.scenariosTitle}</h3>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {c.scenarios.map((s, i) => (
            <BlurFade key={s.title} delay={0.05 * i}>
              <div className="h-full rounded-2xl border bg-card p-6">
                <h4 className="text-xl font-semibold">{s.audience}</h4>
                <div className="mt-1.5 text-sm font-medium text-primary">{s.title}</div>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{s.body}</p>
              </div>
            </BlurFade>
          ))}
        </div>
      </section>

      {/* 04 文档 */}
      <section className="mt-24">
        <SectionHead no={4} label={c.docsLabel} title={c.docsTitle} />
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {c.docs.map((d) => (
            <a
              key={d.href}
              href={url(d.href)}
              className="group rounded-2xl border bg-card p-6 transition-colors hover:border-primary/50"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-muted-foreground">{d.group}</span>
                <ArrowRightIcon className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </div>
              <div className="mt-3 text-lg font-medium">{d.title}</div>
              <p className="mt-1 text-sm text-muted-foreground">{d.summary}</p>
            </a>
          ))}
        </div>
      </section>

      {/* 05 结尾 CTA */}
      <BlurFade>
        <section className="my-24">
          <div className="relative overflow-hidden rounded-3xl border bg-card p-8 sm:p-12">
            <AuroraBackground intensity="subtle" />
            <div className="relative grid items-center gap-10 sm:grid-cols-[1.15fr_0.85fr]">
              <div>
                <div className="flex items-end gap-5">
                  <span className="font-mono text-5xl font-semibold leading-[0.8] text-primary/35 sm:text-6xl">
                    {pad(5)}
                  </span>
                  <div className="text-xs font-medium uppercase tracking-widest text-primary">
                    {c.ctaLabel}
                  </div>
                </div>
                <h2 className="mt-5 text-3xl font-bold tracking-tight sm:text-5xl">{c.ctaTitle}</h2>
                <p className="mt-4 max-w-xl text-muted-foreground">{c.ctaSub}</p>
                <div className="mt-6 flex flex-wrap gap-2">
                  {c.ctaChips.map((chip) => (
                    <span key={chip} className="rounded-full border px-3 py-1 text-xs">
                      {chip}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border bg-background p-6 sm:rotate-1">
                <a
                  href={`${repo}/releases/latest`}
                  className={buttonVariants({
                    size: "lg",
                    className: "h-11 w-full px-6 text-base",
                  })}
                >
                  {c.ctaButton} <ArrowRightIcon className="size-4" />
                </a>
                <p className="mt-3 text-xs leading-6 text-muted-foreground">{c.ctaHint}</p>
                <a
                  href={url(c.docs[0]!.href)}
                  className="mt-3 flex items-center justify-end gap-1 text-sm text-muted-foreground hover:text-foreground"
                >
                  {c.docs[0]!.title} <ArrowRightIcon className="size-3.5" />
                </a>
              </div>
            </div>
          </div>
        </section>
      </BlurFade>
    </main>
  );
}
