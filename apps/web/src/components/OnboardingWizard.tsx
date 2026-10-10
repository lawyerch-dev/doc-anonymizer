import { useEffect, useRef, useState } from "react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@doc-anonymizer/ui/primitives/dialog";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { humanSize } from "../lib/formats";
import * as api from "../lib/api";
import type { ConfigRow, PrepareState } from "../types";

const STORAGE_KEY = "docanon.onboarded";

/* 向导只展示三个方案: 通用 / 最准 / 最快(过滤掉"法律文书交付" —— 那是内部兜底, 不是给用户选的)。
   展示顺序即下面这个顺序。 */
const SHOWN: string[] = ["onnx.yaml", "llm.yaml", "default.yaml"];
const DEFAULT_PICK = "onnx.yaml";   // 默认选中「通用」

/* 每个方案只讲两句: 会脱敏什么 / 限制是什么。不出现模型、下载、识别器等词。 */
const SCHEME_INFO: Record<string, { label: string; desc: string }> = {
  "onnx.yaml": { label: "通用", desc: "脱电话号码、证件、人名、机构、地址。机构与地址会被换掉，标注不出处。" },
  "llm.yaml": { label: "最准", desc: "脱号码、人名、机构、地址，还认得住复杂说法。金额也可能一起被换掉。" },
  "default.yaml": { label: "最快", desc: "只脱电话号码、证件、卡号这类格式固定的号码。人名、机构、地址不处理。" },
};

type Props = {
  configs: ConfigRow[];
  /** 当前正在用的方案(与设置里 L1 下拉一致): 向导里默认高亮它, 没选过就选「通用」 */
  currentConfig: string | null;
  /** 选中的方案 → 让界面也切过去(与设置里 L1 下拉同一路径) */
  onPickConfig: (name: string) => void;
  /** 准备完成后让上层重取模型目录(设置里"已装"标记要跟着变) */
  onModelsChanged: () => void;
  onDone: () => void;
};

/** 本地记"看完引导了"。关掉再来一次的时候不弹。 */
export function hasDoneOnboarding(): boolean {
  return localStorage.getItem(STORAGE_KEY) === "1";
}
export function markOnboardingDone() {
  localStorage.setItem(STORAGE_KEY, "1");
}
export function clearOnboarding() {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * 首次使用的欢迎向导 —— 只有两件事: 选个方案 + 后台把该准备的准备好。
 *
 * 对用户**不出现任何技术词**: 不提模型、下载、识别器、镜像、文件数; 准备过程就一句"正在准备"。
 * 方案列表与设置里 L1 下拉同源(后端 yaml 注释 → label + hint)。骨架复用共享 Dialog。
 */
export function OnboardingWizard({ configs, currentConfig, onPickConfig, onModelsChanged, onDone }: Props) {
  const shown = [...configs].filter((c) => SHOWN.includes(c.name));
  const ordered = [...SHOWN].map((name) => shown.find((c) => c.name === name)).filter(Boolean) as ConfigRow[];

  const [phase, setPhase] = useState<"welcome" | "pick" | "prepare">("welcome");
  // 默认选中: 当前正在用(若是三个之一) → 否则「通用」
  const [picked, setPicked] = useState<string>(
    () => (SHOWN.includes(currentConfig ?? "") ? currentConfig! : DEFAULT_PICK),
  );
  const [prep, setPrep] = useState<PrepareState | null>(null);
  const [busy, setBusy] = useState(false);

  // 回调放 ref: 上层传内联函数时每渲染都是新身份, 会让下面的轮询 effect 反复重建
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  const modelsRef = useRef(onModelsChanged);
  modelsRef.current = onModelsChanged;

  useEffect(() => {
    if (SHOWN.includes(currentConfig ?? "")) setPicked(currentConfig!);
  }, [currentConfig]);

  const finish = () => { markOnboardingDone(); doneRef.current(); };

  // 准备中: 轮询进度。完成就收尾 —— 用户不需要知道下了什么, 只要"能用了"。
  useEffect(() => {
    if (phase !== "prepare" || prep?.state !== "running") return;
    let alive = true;
    const timer = window.setInterval(() => {
      api.prepareStatus().then((s) => {
        if (!alive) return;
        setPrep(s);
        if (s.state === "done") { modelsRef.current(); finish(); }
      }).catch(() => { /* 拉不到就保持上一次显示, 下一次轮询会纠正 */ });
    }, 600);
    return () => { alive = false; window.clearInterval(timer); };
  }, [phase, prep?.state]);   // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    onPickConfig(picked);        // 先把方案切过去, 再按它准备
    setBusy(true);
    try {
      const s = await api.startPrepare(picked);
      if (s.state === "done") { modelsRef.current(); finish(); return; }
      setPrep(s);
      setPhase("prepare");
    } catch (e) {
      setPrep({ state: "error", done_bytes: 0, total_bytes: null, error: (e as Error).message });
      setPhase("prepare");
    } finally {
      setBusy(false);
    }
  };

  const cancelPrep = async () => {
    try { setPrep(await api.cancelPrepare()); } catch { /* 下一次轮询会给出真实状态 */ }
  };

  const pct = prep?.total_bytes ? Math.min(100, Math.round((prep.done_bytes / prep.total_bytes) * 100)) : null;

  return (
    <Dialog open onOpenChange={onDone}>
      <DialogContent className="w-[min(560px,92vw)] max-w-none! gap-0">
        <DialogHeader className="border-b pr-12">
          <DialogTitle>
            {phase === "welcome" ? "欢迎使用文档脱敏工具" : phase === "pick" ? "先选个方案" : "正在准备"}
          </DialogTitle>
          <DialogDescription>
            {phase === "welcome"
              ? "选一个方案，点「开始」就能用。"
              : phase === "pick"
                ? "看看每种会抹掉什么，选一个。"
                : "第一次使用要先把识别能力准备好，稍等一下。"}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-auto p-4">
          {phase === "welcome" ? (
            <div className="space-y-1.5 text-sm leading-relaxed">
              <p>文档在这台电脑上就已脱敏，不会离开它。</p>
              <p className="text-muted-foreground">给你留了些内置样例，可以先试一份，再换成自己的文件。</p>
            </div>
          ) : phase === "pick" ? (
            <div className="space-y-2">
              {ordered.map((c) => {
                const info = SCHEME_INFO[c.name];
                const on = picked === c.name;
                return (
                  <button
                    key={c.name}
                    onClick={() => setPicked(c.name)}
                    aria-pressed={on}
                    className={`flex w-full items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                      on
                        ? "border-selected bg-selected/10 ring-1 ring-selected/40"
                        : "border-input hover:bg-accent/50"
                    }`}
                  >
                    {/* 自绘单选圆点: 用 flex 居中, 不靠位移算像素(位移写法在不同字号下会错位) */}
                    <span
                      aria-hidden
                      className={`mt-0.5 flex size-4 flex-none items-center justify-center rounded-full border-2 ${
                        on ? "border-selected" : "border-muted-foreground/40"
                      }`}
                    >
                      {on ? <span className="block size-1.5 rounded-full bg-selected" /> : null}
                    </span>
                    <span className="min-w-0">
                      <span className={on ? "font-semibold" : "font-medium"}>
                        {info?.label ?? c.label}
                        {c.name === DEFAULT_PICK ? (
                          <span className="ml-1.5 rounded bg-muted px-1 py-px text-[10px] font-normal text-muted-foreground">
                            默认
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                        {info?.desc ?? c.hint}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="space-y-3 py-1">
              {prep?.state === "error" ? (
                <p className="text-sm text-destructive">{prep.error || "准备失败，请检查网络后重试。"}</p>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    正在准备好识别能力，请稍候 —— 只需这一次。
                  </p>
                  <div className="h-1.5 w-full overflow-hidden rounded bg-muted">
                    <div
                      className={`h-full bg-selected transition-[width] duration-300 ${
                        pct === null ? "w-1/3 animate-pulse" : ""
                      }`}
                      style={pct === null ? undefined : { width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-xs tabular-nums text-muted-foreground">
                    {prep?.total_bytes
                      ? `${humanSize(prep.done_bytes)} / ${humanSize(prep.total_bytes)}（${pct}%）`
                      : "正在连接…"}
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t p-3.5">
          {phase === "welcome" ? <span /> : phase === "pick" ? (
            <Button variant="ghost" size="sm" onClick={() => setPhase("welcome")}>返回</Button>
          ) : prep?.state === "error" ? (
            <Button variant="ghost" size="sm" onClick={finish}>先跳过</Button>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => void cancelPrep()}>取消</Button>
          )}

          {phase === "welcome" ? (
            <Button size="sm" onClick={() => setPhase("pick")}>开始</Button>
          ) : phase === "pick" ? (
            <Button size="sm" disabled={busy} onClick={() => void start()}>
              {busy ? "准备中…" : "就用这个"}
            </Button>
          ) : prep?.state === "error" ? (
            <Button size="sm" onClick={() => void start()}>重试</Button>
          ) : prep?.state === "cancelled" ? (
            <Button size="sm" onClick={() => void start()}>继续准备</Button>
          ) : (
            <span />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
