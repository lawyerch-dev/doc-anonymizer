import type { ReactNode } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@doc-anonymizer/ui/primitives/sheet";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
};

/**
 * 脱敏设置弹窗的外壳: 只管弹窗骨架(遮罩 / 标题 / 滚动区 / Esc 与焦点陷阱),
 * 内容由调用方填 —— 这样"设置放什么"与"设置长什么样"各改各的。
 *
 * 复用共享组件库的 Sheet(base-ui Dialog), 不在 app 里再搓一份弹窗骨架。
 */
export function SettingsSheet({ open, onOpenChange, children }: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {/* 默认 sm:max-w-sm(24rem) 装不下 16 行的策略表, 提到 lg(32rem) */}
      <SheetContent side="right" className="w-full gap-0 sm:max-w-lg!">
        <SheetHeader className="border-b">
          <SheetTitle>脱敏设置</SheetTitle>
          <SheetDescription>
            口径、逐类型策略与检测引擎。改完可直接试跑，满意再保存为「我的配置」。
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
      </SheetContent>
    </Sheet>
  );
}
