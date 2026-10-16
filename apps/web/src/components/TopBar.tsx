import type { RefObject } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Logo } from "./Logo";

type Theme = "light" | "dark";

type Props = {
  version: string | null;
  /** 配置有未落盘/已改影子时, 在「设置」后标一个点 */
  configDirty: boolean;
  /** 批次产物: zip + 含原文的映射表 */
  batchOutput?: { folder: string; zipUrl: string; mappingUrl: string } | null;
  /** 脱敏还原(抽屉在 RestorePanel): 只有产物可还原(有锚点)时才可用 */
  restoreDisabled: boolean;
  onOpenRestore: () => void;
  onOpenSettings: () => void;
  onOpenLog: () => void;
  logDisabled: boolean;
  logBtnRef: RefObject<HTMLButtonElement | null>;
  theme: Theme;
  onToggleTheme: () => void;
};

/**
 * 顶部工具栏: 品牌区 + 取走产物 + 右侧设置杂项。
 * 上传/选文件夹入口在文件列表面板, 一键脱敏在其底部(见 PresetList);
 * 方案切换在设置里(顶栏不放快捷入口)。
 * 纯展示组件: 所有 handler 与状态都在 App。
 */
export function TopBar({
  version, configDirty,
  batchOutput, restoreDisabled, onOpenRestore, onOpenSettings, onOpenLog, logDisabled, logBtnRef, theme, onToggleTheme,
}: Props) {
  return (
    <header className="flex h-12 flex-none items-center gap-2 border-b bg-card px-3">
      <Logo className="size-6 flex-none" />
      <h1 className="flex-none text-[15px] font-semibold">文档脱敏工具</h1>
      <span className="hidden flex-none text-xs tabular-nums text-muted-foreground sm:inline">
        {version ? `v${version} · ` : ""}陈恒律师自研自用
      </span>

      {/* 主操作区: 只剩批次产物取走(一键脱敏在文件列表面板底部; 单份产物在 outputs/ 目录自取) */}
      <div className="ml-2 flex items-center gap-1.5">
        {batchOutput?.zipUrl ? (
          <a
            id="downloadZip"
            href={`${batchOutput.zipUrl}?name=${encodeURIComponent(batchOutput.folder)}`}
            download
            className="inline-flex h-7 items-center rounded-[min(var(--radius-md),12px)] border border-border px-2.5 text-[0.8rem] font-medium hover:bg-muted"
          >
            打包下载
          </a>
        ) : null}
        {batchOutput?.mappingUrl ? (
          <a
            href={batchOutput.mappingUrl}
            download
            title="映射表含原文, 切勿与脱敏件一起外发"
            className="hidden flex-none text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground lg:inline"
          >
            映射表
          </a>
        ) : null}
      </div>

      <div className="ml-auto flex items-center gap-1">
        {/* 脱敏还原: 还原是低频动作, 从侧栏卡片收进顶栏入口(抽屉见 RestorePanel)。
            title 挂在 span 上 —— 禁用态的按钮不触发鼠标事件, 自己带 title 是弹不出来的。 */}
        <span title={restoreDisabled ? "跑完一次可还原的脱敏后可用（脱敏方案需保留锚点）" : "把 AI 改好的文件交回来，锚点填回原文"}>
          <Button variant="ghost" size="xs" disabled={restoreDisabled} onClick={onOpenRestore}>
            脱敏还原
          </Button>
        </span>
        <Button variant="ghost" size="xs" onClick={onOpenSettings} title="设置：上传收件规则与脱敏方案">
          ⚙ 设置{configDirty ? " •" : ""}
        </Button>
        <Button ref={logBtnRef} variant="ghost" size="xs" disabled={logDisabled} onClick={onOpenLog}>
          运行日志
        </Button>
        <Button variant="ghost" size="xs" onClick={onToggleTheme} title="切换明暗">
          {theme === "dark" ? "☀ 浅色" : "🌙 深色"}
        </Button>
      </div>
    </header>
  );
}
