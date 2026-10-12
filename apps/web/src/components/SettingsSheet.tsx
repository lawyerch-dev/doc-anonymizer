import type { ReactNode } from "react";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@doc-anonymizer/ui/primitives/sheet";
import { Button } from "@doc-anonymizer/ui/primitives/button";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 设置里改完自动保存的状态(显示在标题右边, 不用滑到底部才知道存没存) */
  saveState: "idle" | "saving" | "saved" | "error";
  saveError?: string | null;
  /** 有没有改过东西可恢复(没有就禁用"恢复默认", 但按钮一直在 —— 不然没人知道有这功能) */
  canReset: boolean;
  onReset: () => void;
  /** 设置里"重新查看欢迎引导": 关掉抽屉再弹向导 */
  onReplayIntro: () => void;
  children: ReactNode;
};

/** 标题右边那句话: 空闲时说清"不用手动存", 存盘过程中的两个状态说人话 */
const SAVE_HINT = {
  idle: "改完自动保存",
  saving: "正在保存…",
  saved: "已自动保存",
} as const;

/**
 * 脱敏设置弹窗的外壳: 只管弹窗骨架(遮罩 / 标题 / 滚动区 / Esc 与焦点陷阱),
 * 内容由调用方填 —— 这样"设置放什么"与"设置长什么样"各改各的。
 *
 * 复用共享组件库的 Sheet(base-ui Dialog), 不在 app 里再搓一份弹窗骨架。
 */
export function SettingsSheet(props: Props) {
  const { open, onOpenChange, saveState, saveError, canReset, onReset, onReplayIntro, children } = props;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {/* 默认 sm:max-w-sm(24rem) 装不下 16 行的策略表。给到 2xl(42rem) 才不"小气":
          策略表 + 模型选项都需要横向空间, 挤在 32rem 里每一列都窄。
          sheet-close: 组件库默认 top-3(12px) 是按 p-4 的头部定的, 这个头部是 py-5 + 18px 标题,
          照默认值关闭按钮会比标题中线高 8px; 抬到 20px 才和标题同一条视觉中线。 */}
      <SheetContent side="right" className="w-full gap-0 sm:max-w-2xl! **:data-[slot=sheet-close]:top-5">
        <SheetHeader className="gap-1 border-b px-6 py-5">
          {/* pr-8 给右上角那个关闭按钮让位: 状态字靠右时不能钻到它底下。
             居中而不是基线对齐: 18px 标题与 12px 状态字的基线对齐会把小字压到标题下方 2px,
              看上去"没对齐"; 居中让两者的墨迹中线重合。 */}
          <div className="flex items-center gap-2 pr-8">
            <SheetTitle className="text-lg">设置</SheetTitle>
            <span className="ml-auto min-w-0 truncate text-xs text-muted-foreground" aria-live="polite">
              {saveState === "error"
                ? <span className="text-destructive">保存失败：{saveError}</span>
                : SAVE_HINT[saveState]}
            </span>
          </div>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-6">{children}</div>
        <SheetFooter className="border-t px-6 py-3">
          <div className="flex items-center justify-between gap-2">
            {/* 恢复默认放这儿而不是折起来的「脱敏方案」里面: 它在收起的抽屉里没人看得见。
                title 挂在 span 上 —— 禁用态的按钮不触发鼠标事件, 自己带 title 是弹不出来的。 */}
            <span title={canReset
              ? "清掉你改过的方案，回到出厂的「通用」（从外面导入的配置文件不会被删）"
              : "还没有改动可恢复"}>
              <Button variant="outline" size="sm" disabled={!canReset} onClick={onReset}>
                恢复默认
              </Button>
            </span>
            <Button variant="ghost" size="sm" onClick={onReplayIntro}>
              重新查看欢迎引导
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
