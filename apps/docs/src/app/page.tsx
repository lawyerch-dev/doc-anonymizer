import Link from "next/link";
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
import { BlurFade } from "@/components/velora/blur-fade";
import { Marquee } from "@/components/velora/marquee";
import { NumberTicker } from "@/components/velora/number-ticker";
import { buttonVariants } from "@/components/ui/button";
import { groupedDocs } from "@/lib/docs";

const ENTITY_TYPES = [
  "PERSON", "PHONE", "ID_CARD", "BANK_CARD", "EMAIL", "IP",
  "LOCATION", "ORG", "AMOUNT", "SECRET", "CUSTOM", "USCC",
];

const FEATURES = [
  { icon: LanguagesIcon, title: "中文优先", body: "规则 + 中文词典 + 两个中文 NER 模型并集，专治中文文档里的姓名与机构。" },
  { icon: WifiOffIcon, title: "全离线", body: "没有任何云端调用；可选的本地大模型路线也只连本机 llama-server。" },
  { icon: FileTextIcon, title: "保留原格式", body: "docx 按 run 改写、xlsx/csv 改单元格、pdf/图片涂黑，前后可左右对照。" },
  { icon: FingerprintIcon, title: "不许静默少一层", body: "引擎起不来就在跑前报错退出，不产出“少了识别”的结果。" },
  { icon: ShieldCheckIcon, title: "召回优先", body: "拿不准的一律标出；命中位置与来源在运行日志里逐条可查。" },
  { icon: RefreshCwIcon, title: "可续跑可还原", body: "账本每文件落盘，--resume 不重做；mapping.json 能把文本产物还原回去。" },
];

const STATS = [
  { value: 4, suffix: "", label: "检测引擎（规则/词典/ONNX NER/LLM）" },
  { value: 34, suffix: "ms", label: "ONNX 路线每例耗时（实测）" },
  { value: 8, suffix: " 种", label: "输入格式（含扫描件与图片）" },
  { value: 0, suffix: "", label: "运行期网络请求" },
];

export default function Home() {
  return (
    <main className="flex-1">
      <section className="mx-auto max-w-5xl px-6 pt-20 pb-12">
        <BlurFade>
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs text-muted-foreground">
            <LockIcon className="size-3.5" /> MIT · 本地运行 · 不联网
          </p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            把中文文档里的敏感信息，
            <br />
            在<span className="text-primary">本机</span>抹掉
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            人名、手机号、身份证、银行卡、邮箱、IP、统一社会信用代码、密钥、自定义词 —— 识别并替换，
            输出与原文格式相同的文件，外加一份可还原的对照表。
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/docs/quickstart" className={buttonVariants({ size: "lg" })}>
              5 分钟快速上手 <ArrowRightIcon className="size-4" />
            </Link>
            <a
              href="https://github.com/lawyerch/doc-anonymizer"
              className={buttonVariants({ size: "lg", variant: "outline" })}
            >
              GitHub
            </a>
          </div>
        </BlurFade>
      </section>

      <BlurFade delay={0.1}>
        <section className="border-y py-6">
          <Marquee pauseOnHover className="[--duration:38s]">
            {ENTITY_TYPES.map((t) => (
              <span key={t} className="mx-2 rounded-md border bg-card px-3 py-1 font-mono text-sm">
                {t}
              </span>
            ))}
          </Marquee>
        </section>
      </BlurFade>

      <section className="mx-auto grid max-w-5xl grid-cols-2 gap-6 px-6 py-14 sm:grid-cols-4">
        {STATS.map((s, i) => (
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
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-16">
        <h2 className="mb-6 text-2xl font-semibold">特性</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <BlurFade key={f.title} delay={0.05 * i}>
              <div className="h-full rounded-xl border bg-card p-5">
                <f.icon className="size-5 text-primary" />
                <h3 className="mt-3 font-medium">{f.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{f.body}</p>
              </div>
            </BlurFade>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <h2 className="mb-6 text-2xl font-semibold">文档</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groupedDocs().flatMap((g) =>
            g.items.map((d) => (
              <Link
                key={d.slug}
                href={`/docs/${d.slug}`}
                className="rounded-xl border bg-card p-5 transition-colors hover:border-primary/50"
              >
                <div className="text-xs text-muted-foreground">{g.group}</div>
                <div className="mt-1 font-medium">{d.title}</div>
                <p className="mt-1 text-sm text-muted-foreground">{d.summary}</p>
              </Link>
            )),
          )}
        </div>
      </section>

      <footer className="border-t px-6 py-8 text-sm text-muted-foreground">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <span>
            MIT © 2026 lawyerch · 组件来自{" "}
            <a className="underline" href="https://github.com/ColorlibHQ/velora-ui">
              velora-ui
            </a>
            （MIT）
          </span>
          <span>Next.js 16 · Tailwind CSS 4 · 静态导出</span>
        </div>
      </footer>
    </main>
  );
}
