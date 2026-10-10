import type { ReactNode } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@doc-anonymizer/ui/primitives/sheet";
import { Button } from "@doc-anonymizer/ui/primitives/button";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 设置里"重新查看欢迎引导": 关掉抽屉再弹向导 */
  onReplayIntro: () => void;
  children: ReactNode;
};

/**
 * 脱敏设置弹窗的外壳: 只管弹窗骨架(遮罩 / 标题 / 滚动区 / Esc 与焦点陷阱),
 * 内容由调用方填 —— 这样"设置放什么"与"设置长什么样"各改各的。
 *
 * 复用共享组件库的 Sheet(base-ui Dialog), 不在 app 里再搓一份弹窗骨架。
 */
export function SettingsSheet({ open, onOpenChange, onReplayIntro, children }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {/* 默认 sm:max-w-sm(24rem) 装不下 16 行的策略表。给到 2xl(42rem) 才不"小气":
          策略表 + 模型选项都需要横向空间, 挤在 32rem 里每一列都窄。 */}
      <SheetContent side="right" className="w-full gap-0 sm:max-w-2xl!">
        <SheetHeader className="gap-1 border-b px-6 py-5">
          <SheetTitle className="text-lg">脱敏设置</SheetTitle>
          <SheetDescription className="text-pretty">
            方案、逐类型策略与检测引擎。改完可直接试跑，满意再保存为「我的配置」。
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-6">{children}</div>
        <SheetFooter className="border-t px-6 py-3">
          <Button variant="ghost" size="sm" onClick={onReplayIntro}>
            重新查看欢迎引导
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
