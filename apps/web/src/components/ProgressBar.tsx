import { Button } from "@doc-anonymizer/ui/primitives/button";

type Props = {
  /** 当前阶段一句话 + 百分比(progressInfo 算好) */
  runInfo: { label: string; pct: number | null };
  elapsed: number;
  onCancel: () => void;
};

/**
 * 跑批/单份脱敏进行中的进度条 —— 放在底部状态条(footer)中间。
 * 原来是「脱敏后」预览格里的遮罩卡, 现在压成一行: 阶段文案 + 细进度条 + 已用秒数 + 取消。
 * (#progress / #cancelRun 是 E2E 契约钩子, 与界面位置无关, 不许改名)
 */
export function ProgressBar({ runInfo, elapsed, onCancel }: Props) {
  return (
    <div id="progress" className="mx-auto flex min-w-0 flex-1 items-center justify-center gap-2">
      <span className="min-w-0 truncate">{runInfo.label}</span>
      <span className="h-1 w-24 flex-none overflow-hidden rounded bg-muted">
        {runInfo.pct !== null ? (
          <span
            className="block h-full bg-selected transition-[width] duration-300"
            style={{ width: `${runInfo.pct}%` }}
          />
        ) : (
          /* 起模型/读文件/写回这几段没有百分比 —— 一根来回走的条证明"还活着" */
          <span className="animate-indeterminate block h-full w-1/4 rounded-full bg-selected" />
        )}
      </span>
      <span className="flex-none tabular-nums">{elapsed}s</span>
      <Button
        id="cancelRun"
        variant="ghost"
        size="xs"
        className="h-4 px-1.5 text-[11px]"
        onClick={onCancel}
      >
        取消
      </Button>
    </div>
  );
}
