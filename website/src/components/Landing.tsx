import { ArrowRightIcon, FileTextIcon, FingerprintIcon, LanguagesIcon, LockIcon, RefreshCwIcon, ShieldCheckIcon, WifiOffIcon } from "lucide-react";
import { BlurFade } from "@doc-anonymizer/ui/blur-fade";
import { Marquee } from "@doc-anonymizer/ui/marquee";
import { NumberTicker } from "@doc-anonymizer/ui/number-ticker";
import { buttonVariants } from "@doc-anonymizer/ui/primitives/button";
import { AnimatedGradientText } from "@doc-anonymizer/ui/animated-gradient-text";
import { AuroraBackground } from "@doc-anonymizer/ui/aurora-background";
import { BorderBeam } from "@doc-anonymizer/ui/border-beam";

const ENTITY_TYPES = ["PERSON", "PHONE", "ID_CARD", "BANK_CARD", "EMAIL", "IP", "LOCATION", "ORG", "AMOUNT", "SECRET", "CUSTOM", "USCC"];

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

const DOC_LINKS = [
  { href: "/start/quickstart/", group: "开始", title: "快速上手", summary: "5 分钟跑通 + 常见问题" },
  { href: "/start/readme/", group: "开始", title: "使用手册", summary: "命令、产物、配置、引擎与已知限制" },
  { href: "/dev/architecture/", group: "开发", title: "架构与目录设计", summary: "五包结构、硬边界、决策记录" },
  { href: "/dev/contributing/", group: "开发", title: "贡献指南", summary: "环境、测试、提交与 PR" },
  { href: "/dev/agents/", group: "开发", title: "开发契约", summary: "不能违反的边界、命令与坑" },
  { href: "/other/security/", group: "其他", title: "安全策略", summary: "漏脱敏怎么报、设计上的边界" },
];

export default function Landing({ repo }: { repo: string }) {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <div className="relative -mx-6 mb-10 overflow-hidden rounded-2xl border">
        <AuroraBackground intensity="medium" />
        <div className="relative px-6 py-14">
          <h2 className="text-2xl font-semibold">
            velora 全量组件已就位：
            <AnimatedGradientText>100 个组件 + 31 个区块</AnimatedGradientText>
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            共享包 <code>apps/ui</code> 里，产品界面与文档站共用同一套。
          </p>
        </div>
      </div>
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
          <a href="/start/quickstart/" className={buttonVariants({ size: "lg" })}>
            5 分钟快速上手 <ArrowRightIcon className="size-4" />
          </a>
          <a href={repo} className={buttonVariants({ size: "lg", variant: "outline" })}>
            GitHub
          </a>
        </div>
      </BlurFade>

      <BlurFade delay={0.1}>
        <section className="mt-14 border-y py-6">
          <Marquee pauseOnHover className="[--duration:38s]">
            {ENTITY_TYPES.map((t) => (
              <span key={t} className="mx-2 rounded-md border bg-card px-3 py-1 font-mono text-sm">{t}</span>
            ))}
          </Marquee>
        </section>
      </BlurFade>

      <section className="mt-12 grid grid-cols-2 gap-6 sm:grid-cols-4">
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

      <section className="mt-16">
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

      <section className="mt-16">
        <div className="relative overflow-hidden rounded-2xl border bg-card p-6">
          <BorderBeam />
          <h2 className="text-xl font-semibold">装上就能用</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <code>{'import { Marquee } from "@doc-anonymizer/ui/marquee"'}</code> ——
            区块用 <code>@doc-anonymizer/ui/blocks/hero-globe</code>，基础件用
            <code>@doc-anonymizer/ui/primitives/button</code>。
          </p>
        </div>
      </section>

      <section className="mt-16">
        <h2 className="mb-6 text-2xl font-semibold">文档</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DOC_LINKS.map((d) => (
            <a key={d.href} href={d.href} className="rounded-xl border bg-card p-5 transition-colors hover:border-primary/50">
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
