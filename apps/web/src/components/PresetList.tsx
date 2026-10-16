import { useRef, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import type { DocRow, DocStatus } from "../types";
import { totalCounts } from "../lib/api";

/** 还没选文件时的三步引导(窄栏里放不下长文案, 只给动作词) */
const STEPS = ["上传文件", "点击一键脱敏", "检查效果"];

/** 状态筛选: 与文件行的状态徽标同一套词 */
const FILTERS: { id: "all" | DocStatus; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "idle", label: "待跑" },
  { id: "ok", label: "已脱敏" },
  { id: "unsupported", label: "未处理" },
  { id: "error", label: "失败" },
];

/** 扩展名 → 行首的小类型徽标(LawRedact 式): 认不出的显示扩展名本身 */
const TYPE_BADGE: Record<string, string> = {
  pdf: "PDF", doc: "DOC", docx: "DOC", xls: "XLS", xlsx: "XLS",
  ppt: "PPT", pptx: "PPT", txt: "TXT", md: "MD", markdown: "MD", csv: "CSV",
  png: "PNG", jpg: "JPG", jpeg: "JPG", webp: "WEBP", bmp: "BMP", tif: "TIF", tiff: "TIF",
};

function badgeOf(name: string): string {
  const ext = (name.split(".").pop() ?? "").toLowerCase();
  if (!ext || ext === name.toLowerCase()) return "文件";
  return TYPE_BADGE[ext] ?? ext.slice(0, 4).toUpperCase();
}

/**
 * 状态徽标: 已处理好的显示"✓ 抹了多少处", 没处理好的显示它的状态。
 * 颜色只用既有的三系(selected / destructive / muted), 不引入新色。
 */
const BADGE: Record<DocStatus, { text: string; cls: string }> = {
  idle: { text: "待跑", cls: "text-muted-foreground" },
  running: { text: "跑中…", cls: "text-foreground" },
  ok: { text: "", cls: "text-selected" },
  unsupported: { text: "未处理", cls: "text-muted-foreground" },
  error: { text: "失败", cls: "text-destructive" },
};

type Props = {
  rows: DocRow[];
  /** 当前选中的行(键), 与列表同一套键 */
  activeKey: string | null;
  loading: boolean;
  // 是否已经点过「加载示例」: 区分"还没加载"(给引导文案)与"加载过但 samples/ 是空的"
  loaded: boolean;
  uploading: boolean;
  /** 正在上传第几份(批量上传时用) */
  uploadProgress: { done: number; total: number } | null;
  /** 当前是不是一个文件夹批次; 是的话列表上方标出是哪个文件夹 */
  folderName: string | null;
  /** 环境支不支持选文件夹(webkitdirectory) —— 不支持就不显示入口, 不装作能用 */
  hasFolderPicker: boolean;
  /** 当前收件规则的一句话(收哪些类型 / 要不要子文件夹): 与设置面板同一处措辞 */
  ruleSummary: string;
  /** 去设置里改收件规则 */
  onEditRule: () => void;
  /** 上一批跳过了什么(只计数, 不进列表)。null = 没有可说的 */
  skipNote: string | null;
  onPick: (row: DocRow) => void;
  onPickFolder: (files: File[]) => void;
  onExitFolder: () => void;
  onRefresh: () => void;
  onUpload: (files: File[]) => void;
  /** 一键脱敏: 固定在面板底部(原先在顶栏)。#run 是 E2E 契约钩子, 只在有东西可跑时出现 */
  canRun: boolean;
  runLabel: string;
  runDisabled: boolean;
  onRun: () => void;
};

export function PresetList({
  rows, activeKey, loading, loaded, uploading, uploadProgress, folderName, hasFolderPicker,
  ruleSummary, onEditRule, skipNote, onPick, onPickFolder, onExitFolder, onRefresh, onUpload,
  canRun, runLabel, runDisabled, onRun,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DocStatus>("all");

  const filtered = rows.filter((r) =>
    (statusFilter === "all" || r.status === statusFilter)
    && r.name.toLowerCase().includes(query.trim().toLowerCase()));
  const okCount = rows.filter((r) => r.status === "ok").length;
  const hitTotal = rows.reduce((n, r) => n + (r.status === "ok" ? totalCounts(r.counts) : 0), 0);

  return (
    <div className="flex min-h-56 flex-1 flex-col rounded-xl border bg-card p-3.5">
      <div className="mb-2.5 flex flex-none items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-[13px] font-semibold tracking-wide text-muted-foreground">
          文件列表
          <span className="rounded bg-muted px-1.5 py-px text-[10px] font-medium tabular-nums">
            {rows.length}
          </span>
        </h3>
        <Button
          id="loadSamples"
          variant="ghost"
          size="xs"
          onClick={onRefresh}
          disabled={loading}
          title="从 samples/ 载入内置测试文档"
        >
          加载示例
        </Button>
      </div>

      {/* 搜索与状态筛选: 文件一多, 靠名字与状态各收一道 */}
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="搜索文件名…"
        aria-label="搜索文件名"
        className="mb-2 w-full flex-none rounded-lg border bg-background px-2.5 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground/70 focus-visible:ring-2 focus-visible:ring-ring"
      />
      <div className="mb-2.5 flex flex-none flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            aria-pressed={statusFilter === f.id}
            onClick={() => setStatusFilter(f.id)}
            className={`rounded-full px-2 py-0.5 text-[11px] transition-colors ${
              statusFilter === f.id
                ? "bg-foreground font-medium text-background"
                : "border text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {folderName ? (
        <p className="mb-2.5 flex flex-none items-center gap-2 text-[11px] text-muted-foreground">
          <span className="min-w-0 flex-1 truncate" title={folderName}>
            文件夹：{folderName}（{rows.length} 份）
          </span>
          <button
            type="button"
            className="flex-none underline underline-offset-2 hover:text-foreground"
            onClick={onExitFolder}
          >
            返回
          </button>
        </p>
      ) : null}

      {folderName && skipNote ? (
        <p className="mb-2.5 flex-none text-[11px] leading-snug text-muted-foreground" title={skipNote}>
          {skipNote}
        </p>
      ) : null}

      {/* 收件规则只在设置里改(单一出处), 这里只报"现在按什么收" + 一个入口 */}
      {folderName ? (
        <p className="mb-2.5 flex flex-none items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="min-w-0 flex-1 truncate" title={ruleSummary}>{ruleSummary}</span>
          <button
            type="button"
            id="editUploadRule"
            className="flex-none underline underline-offset-2 hover:text-foreground"
            onClick={onEditRule}
          >
            改
          </button>
        </p>
      ) : null}

      {/* 选文件夹: 保留相对层级(webkitRelativePath), 一批一次跑完。
          批次里也留着这个入口(文案变"换一个文件夹…") —— 否则想换一个得先"返回"再点一次 */}
      {hasFolderPicker ? (
        <>
          <input
            ref={folderRef}
            type="file"
            hidden
            multiple
            // webkitdirectory 是 webkit 前缀属性, React 的 JSX 类型里没有 —— 只能这样塞
            {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
            onChange={(e) => {
              const files = [...(e.target.files ?? [])];
              if (files.length) onPickFolder(files);
              e.target.value = "";
            }}
          />
          <Button
            id="pickFolder"
            variant={folderName ? "outline" : "default"}
            className="mb-2 w-full flex-none"
            disabled={uploading}
            onClick={() => folderRef.current?.click()}
          >
            {uploading && uploadProgress
              ? `上传中 ${uploadProgress.done}/${uploadProgress.total}`
              : folderName ? "换一个文件夹…" : "选择文件夹…"}
          </Button>
        </>
      ) : null}

      <input
        ref={fileRef}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          const files = [...(e.target.files ?? [])];
          if (files.length) onUpload(files);
          e.target.value = "";
        }}
      />
      <Button
        variant={folderName ? "ghost" : "outline"}
        className="mb-2.5 w-full flex-none"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
      >
        {uploading && !uploadProgress ? "上传中…" : "上传本地文件…"}
      </Button>

      {loading ? (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">加载中…</div>
      ) : filtered.length ? (
        <div className="scroll-thin min-h-0 flex-1 overflow-auto overscroll-contain">
          {filtered.map((row) => {
            const active = row.key === activeKey;
            const badge = BADGE[row.status];
            return (
              // 真 <button>: 之前是 `div role="button"` —— 键盘 Enter/Space、焦点环、
              // 屏幕阅读器都的"能按"语义都得自己补, 用原生元素则自带
              // (.preset 这个类名保留给 E2E 的示例项; .doc-row 是这一批新加的钩子)
              <button
                key={row.key}
                type="button"
                aria-pressed={active}
                data-status={row.status}
                className={`${row.kind === "preset" ? "preset " : ""}doc-row mb-1.5 flex w-full cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-[13px] transition-colors ${
                  active
                    ? "border-selected bg-selected font-semibold text-selected-foreground shadow-sm"
                    : "hover:border-primary/60 hover:bg-accent/60"
                }`}
                title={row.reason ? `${row.name} —— ${row.reason}` : row.name}
                onClick={() => onPick(row)}
              >
                {/* 类型徽标是第 1 个 span, 文件名必须是第 2 个 span(E2E 按位置取名字) */}
                <span
                  aria-hidden
                  className={`flex-none rounded px-1 py-0.5 text-center text-[9px] font-semibold tracking-wide ${
                    active ? "bg-selected-foreground/15 text-selected-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {badgeOf(row.name)}
                </span>
                <span className="min-w-0 flex-1 truncate">{row.name}</span>
                {/* 批次里每行都来自同一个文件夹, 来源标签就省了(上面已经写明是哪个文件夹) */}
                {row.kind !== "batch" ? (
                  <span className={`flex-none text-[11px] uppercase ${active ? "text-selected-foreground/80" : "text-muted-foreground"}`}>
                    {row.tag}
                  </span>
                ) : null}
                <span className={`flex-none text-[11px] tabular-nums ${active ? "text-selected-foreground" : badge.cls}`}>
                  {row.status === "ok" ? `✓ ${totalCounts(row.counts)} 处` : badge.text}
                </span>
              </button>
            );
          })}
        </div>
      ) : rows.length ? (
        <div className="flex flex-1 items-center justify-center px-3 text-center text-xs text-muted-foreground">
          没有匹配的文件
        </div>
      ) : folderName ? (
        <div className="flex flex-1 items-center justify-center px-3 text-center text-xs text-muted-foreground">
          这个文件夹里没有可脱敏的文档
        </div>
      ) : loaded ? (
        <div className="flex flex-1 items-center justify-center px-3 text-center text-xs text-muted-foreground">
          samples/ 无可预览示例
        </div>
      ) : (
        <ol className="flex flex-1 flex-col justify-center px-1">
          {STEPS.map((step, i) => (
            <li key={step} className="flex gap-2.5">
              <span className="flex flex-col items-center">
                <span className="flex size-5 flex-none items-center justify-center rounded-full bg-primary text-[11px] font-medium text-primary-foreground">
                  {i + 1}
                </span>
                {/* 连接线: 左列被 align-items:stretch 拉到本行满高, flex-1 吃掉圆点以下的余量; 最后一步不画 */}
                {i < STEPS.length - 1 ? (
                  <span aria-hidden className="w-px flex-1 bg-border" />
                ) : null}
              </span>
              <span className={`text-[13px] leading-5 text-foreground/80 ${i < STEPS.length - 1 ? "pb-5" : ""}`}>
                {step}
              </span>
            </li>
          ))}
        </ol>
      )}

      {/* 底部汇总: 这批一共多少、成了多少、抹了多少处(与 LawRedact 列表底栏同一排法) */}
      {rows.length ? (
        <p className="mt-2 flex-none border-t pt-2 text-[11px] tabular-nums text-muted-foreground">
          共 {rows.length} 份 · 已完成 {okCount}
          {hitTotal ? ` · 命中 ${hitTotal} 处` : ""}
        </p>
      ) : null}

      {/* 一键脱敏: 固定在面板最底部, 列表多长都不挪位(原先在顶栏, 收进来离文件清单更近) */}
      {canRun ? (
        <Button
          id="run"
          className="mt-2 w-full flex-none"
          disabled={runDisabled}
          onClick={onRun}
        >
          {runLabel}
        </Button>
      ) : null}
    </div>
  );
}
