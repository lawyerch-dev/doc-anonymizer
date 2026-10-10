import { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@doc-anonymizer/ui/primitives/dialog";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import type { ConfigRow } from "../types";

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
 * 首次使用的欢迎向导 —— 只选个方案。每个方案就讲"会脱敏什么 + 限制", 不出现模型/下载/识别器这些词。
 * 默认选中「通用」; 若当前已在用某个方案, 就高亮它(与文档选择状态一致)。
 * 方案按钮是单选: 点一下选中, 「就用这个」开始。
 */
export function OnboardingWizard({ configs, currentConfig, onPickConfig, onDone }: Props) {
  const shown = [...configs].filter((c) => SHOWN.includes(c.name));
  const ordered = [...SHOWN].map((name) => shown.find((c) => c.name === name)).filter(Boolean) as ConfigRow[];

  // 默认选中: 当前正在用(若是三个之一) → 否则「通用」
  const [picked, setPicked] = useState<string>(
    () => (SHOWN.includes(currentConfig ?? "") ? currentConfig! : DEFAULT_PICK),
  );
  useEffect(() => {
    if (SHOWN.includes(currentConfig ?? "")) setPicked(currentConfig!);
  }, [currentConfig]);

  const finish = () => { markOnboardingDone(); onDone(); };
  const start = () => { onPickConfig(picked); finish(); };

  return (
    <Dialog open onOpenChange={onDone}>
      <DialogContent className="w-[min(560px,92vw)] max-w-none! gap-0">
        <DialogHeader className="border-b pr-12">
          <DialogTitle>欢迎使用文档脱敏工具</DialogTitle>
          <DialogDescription>选一个方案，点「开始」就能用。</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-auto p-4">
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
        </div>

        <div className="flex items-center justify-between gap-2 border-t p-3.5">
          <span />
          <Button size="sm" onClick={start}>开始</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}