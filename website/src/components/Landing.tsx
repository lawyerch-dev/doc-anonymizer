import {
  ArrowRightIcon,
  FileTextIcon,
  FingerprintIcon,
  LanguagesIcon,
  LockIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  WifiOffIcon,
} from "lucide-react";
import { BlurFade } from "@doc-anonymizer/ui/blur-fade";
import { Marquee } from "@doc-anonymizer/ui/marquee";
import { NumberTicker } from "@doc-anonymizer/ui/number-ticker";
import { buttonVariants } from "@doc-anonymizer/ui/primitives/button";
import type { ReactNode } from "react";
import { url } from "../lib/site";
import { AuroraBackground } from "@doc-anonymizer/ui/aurora-background";
import { COPY, type TrustIcon, type ValueIcon } from "../lib/landing-copy";

const TRUST_ICONS: Record<TrustIcon, typeof WifiOffIcon> = {
  offline: WifiOffIcon,
  format: FileTextIcon,
  restore: RefreshCwIcon,
  loud: ShieldCheckIcon,
};

const VALUE_ICONS: Record<ValueIcon, typeof WifiOffIcon> = {
  chinese: LanguagesIcon,
  legacy: FileTextIcon,
  recall: FingerprintIcon,
};

function H2({ children }: { children: ReactNode }) {
  return <h2 className="mb-6 text-2xl font-semibold">{children}</h2>;
}

/**
 * 产品落地页。中英共用这一个组件 —— 文案在 `src/lib/landing-copy.ts`,
 * 两条路由(`/` 与 `/en/`)只是传不同的 `locale`。
 *
 * 阅读顺序按"普通办公用户"排: 能不能用 → 谁在用 → 怎么用 → 放不放心 →
 * 中文差异点 → 文档。引擎、命令行那类内容不上首页 —— 归文档站。
 */
export default function Landing({ repo, locale }: { repo: string; locale: "zh" | "en" }) {
  const c = COPY[locale];
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <BlurFade>
        <p className="mb-4 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs text-muted-foreground">
          <LockIcon className="size-3.5" /> {c.badge}
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{c.h1}</h1>
        <p className="mt-5 max-w-2xl text-lg text-muted-foreground">{c.sub}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          {/* 下载排第一: 访客来看这个工具, 最想做的事就是拿到它; 次按钮一律 outline。 */}
          <a
            href={`${repo}/releases/latest`}
            className={buttonVariants({ size: "lg", className: "h-11 px-6 text-base" })}
          >
            {c.download} <ArrowRightIcon className="size-4" />
          </a>
          <a
            href="#how"
            className={buttonVariants({ size: "lg", variant: "outline", className: "h-11 px-6 text-base" })}
          >
            {c.cta}
          </a>
        </div>
        {/* 一行说清"装完为什么会拦一下": 不写的话, 用户下载后被系统拦下, 第一反应是这软件坏了 */}
        <p className="mt-3 max-w-2xl text-xs text-muted-foreground">{c.downloadHint}</p>
      </BlurFade>

      <BlurFade delay={0.1}>
        <section className="relative mt-14 overflow-hidden rounded-2xl border">
          <AuroraBackground intensity="subtle" />
          <div className="border-b py-4">
            <Marquee pauseOnHover className="[--duration:38s]">
              {c.entities.map((t) => (
                <span key={t} className="mx-2 rounded-md border bg-card px-3 py-1 text-sm">
                  {t}
                </span>
              ))}
            </Marquee>
          </div>
          <div className="relative grid grid-cols-2 gap-6 px-6 py-8 sm:grid-cols-4">
            {c.stats.map((s, i) => (
              <BlurFade key={s.label} delay={0.05 * i}>
                <div>
                  <div className="text-3xl font-semibold">
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

      <section className="mt-16">
        <H2>{c.scenariosTitle}</H2>
        <div className="grid gap-4 sm:grid-cols-3">
          {c.scenarios.map((s, i) => (
            <BlurFade key={s.title} delay={0.05 * i}>
              <div className="h-full rounded-xl border bg-card p-5">
                <div className="text-xs text-muted-foreground">{s.audience}</div>
                <h3 className="mt-1 font-medium">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.body}</p>
              </div>
            </BlurFade>
          ))}
        </div>
      </section>

      <section id="how" className="mt-16 scroll-mt-8">
        <H2>{c.stepsTitle}</H2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {c.steps.map((s, i) => (
            <BlurFade key={s.title} delay={0.05 * i}>
              <li className="h-full rounded-xl border bg-card p-5">
                <span className="grid size-7 place-items-center rounded-full border text-xs font-medium text-muted-foreground">
                  {i + 1}
                </span>
                <h3 className="mt-3 font-medium">{s.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
              </li>
            </BlurFade>
          ))}
        </ol>
      </section>

      <section className="mt-16">
        <H2>{c.trustTitle}</H2>
        <div className="grid gap-4 sm:grid-cols-2">
          {c.trust.map((t, i) => {
            const Icon = TRUST_ICONS[t.icon];
            return (
              <BlurFade key={t.title} delay={0.05 * i}>
                <div className="flex h-full gap-3 rounded-xl border bg-card p-5">
                  <Icon className="mt-0.5 size-5 shrink-0 text-primary" />
                  <div>
                    <h3 className="font-medium">{t.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{t.body}</p>
                  </div>
                </div>
              </BlurFade>
            );
          })}
        </div>
      </section>

      <section className="mt-16">
        <H2>{c.valueTitle}</H2>
        <div className="grid gap-4 sm:grid-cols-3">
          {c.values.map((v, i) => {
            const Icon = VALUE_ICONS[v.icon];
            return (
              <BlurFade key={v.title} delay={0.05 * i}>
                <div className="h-full rounded-xl border bg-card p-5">
                  <Icon className="size-5 text-primary" />
                  <h3 className="mt-3 font-medium">{v.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{v.body}</p>
                </div>
              </BlurFade>
            );
          })}
        </div>
      </section>

      <section className="mt-16">
        <H2>{c.docsTitle}</H2>
        <div className="grid gap-4 sm:grid-cols-3">
          {c.docs.map((d) => (
            <a
              key={d.href}
              href={url(d.href)}
              className="rounded-xl border bg-card p-5 transition-colors hover:border-primary/50"
            >
              <div className="text-xs text-muted-foreground">{d.group}</div>
              <div className="mt-1 font-medium">{d.title}</div>
              <p className="mt-1 text-sm text-muted-foreground">{d.summary}</p>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}
