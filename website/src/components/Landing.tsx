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
import { url } from "../lib/site";
import { AuroraBackground } from "@doc-anonymizer/ui/aurora-background";
import { COPY, type HeroSegment } from "../lib/landing-copy";

const ENTITY_TYPES = ["PERSON", "PHONE", "ID_CARD", "BANK_CARD", "EMAIL", "IP", "LOCATION", "ORG", "AMOUNT", "SECRET", "CUSTOM", "USCC"];

const ICONS = {
  languages: LanguagesIcon,
  offline: WifiOffIcon,
  format: FileTextIcon,
  loud: FingerprintIcon,
  recall: ShieldCheckIcon,
  resume: RefreshCwIcon,
};

function hero(segments: HeroSegment[]) {
  return segments.map((seg, i) => {
    if ("br" in seg) return <br key={i} />;
    if ("hi" in seg)
      return (
        <span key={i} className="text-primary">
          {seg.hi}
        </span>
      );
    return <span key={i}>{seg.text}</span>;
  });
}

/**
 * 产品落地页。中英共用这一个组件 —— 文案在 `src/lib/landing-copy.ts`，
 * 两条路由(`/` 与 `/en/`)只是传不同的 `locale`。
 */
export default function Landing({ repo, locale }: { repo: string; locale: "zh" | "en" }) {
  const c = COPY[locale];
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <BlurFade>
        <p className="mb-4 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs text-muted-foreground">
          <LockIcon className="size-3.5" /> {c.badge}
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{hero(c.hero)}</h1>
        <p className="mt-5 max-w-2xl text-lg text-muted-foreground">{c.sub}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={url(c.docs[0]!.href)} className={buttonVariants({ size: "lg" })}>
            {c.cta} <ArrowRightIcon className="size-4" />
          </a>
          <a href={repo} className={buttonVariants({ size: "lg", variant: "outline" })}>
            GitHub
          </a>
        </div>
      </BlurFade>

      <BlurFade delay={0.1}>
        <section className="relative mt-14 overflow-hidden rounded-2xl border">
          <AuroraBackground intensity="subtle" />
          <div className="border-b py-4">
            <Marquee pauseOnHover className="[--duration:38s]">
              {ENTITY_TYPES.map((t) => (
                <span key={t} className="mx-2 rounded-md border bg-card px-3 py-1 font-mono text-sm">
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
        <h2 className="mb-6 text-2xl font-semibold">{c.featuresTitle}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {c.features.map((f, i) => {
            const Icon = ICONS[f.icon];
            return (
              <BlurFade key={f.title} delay={0.05 * i}>
                <div className="h-full rounded-xl border bg-card p-5">
                  <Icon className="size-5 text-primary" />
                  <h3 className="mt-3 font-medium">{f.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{f.body}</p>
                </div>
              </BlurFade>
            );
          })}
        </div>
      </section>

      <section className="mt-16">
        <h2 className="mb-6 text-2xl font-semibold">{c.docsTitle}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
