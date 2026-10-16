import type { ReactNode } from "react";

type Props = {
  /** 当前脱敏方案的中文名(设置里与顶栏下拉同一处口径) */
  schemeLabel: string | null;
  version: string | null;
  /** 居中插槽: 跑批/单份脱敏时放 ProgressBar(见 ProgressBar) */
  progress?: ReactNode;
};

/**
 * 底部状态条: 只说三件用户能验证的事 —— 本地离线运行、当前方案、版本号。
 * 不接系统占用(后端 /health 没有这些数据, 不编造)。
 */
export function StatusBar({ schemeLabel, version, progress }: Props) {
  return (
    <footer className="flex h-7 flex-none items-center gap-3 border-t bg-card px-3 text-[11px] text-muted-foreground">
      <span className="flex flex-none items-center gap-1.5">
        <i aria-hidden className="size-1.5 rounded-full bg-primary" />
        本地离线运行
      </span>
      {schemeLabel ? <span className="min-w-0 flex-none truncate">方案：{schemeLabel}</span> : null}
      {progress}
      <span className="ml-auto flex-none tabular-nums">{version ? `v${version}` : ""}</span>
    </footer>
  );
}
