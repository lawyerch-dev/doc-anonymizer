import { useRef, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@doc-anonymizer/ui/primitives/sheet";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import * as api from "../lib/api";
import { DIRECTORY_INPUT_PROPS, HAS_FOLDER_PICKER } from "../lib/dom";
import type { RestoreBatchResp } from "../types";

/** 一份"该有哪些锚点": `name` 是脱敏产物的名字 —— 还原时靠它把锚点清单对回这一份。 */
export type ExpectedFile = { name: string; anchors: Record<string, number> };

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 哪一次脱敏的产物目录(映射表在服务端, 不经浏览器 —— 它就是原文本身) */
  token: string;
  /** 对账时报给人看的名字(单份是文件名, 批次是文件夹名) */
  sourceName: string;
  /** 逐份的锚点清单; 有了它才能报"少了哪些", 没有就只能报"多了哪些" */
  expected?: ExpectedFile[];
  /** 批次模式: 额外给「选文件夹」入口, 结果按逐份列出来 */
  batch?: boolean;
};

/** 后端能还原的格式(与 `restorers._ROUTES` 对齐); pdf/图片原理上还原不了 */
const RESTORABLE_EXT = ["docx", "xlsx", "csv", "txt", "md", "markdown"];

/**
 * 这个入口还没验收完, 先在界面上标「开发中」并禁用 —— 免得用户以为点了没反应。
 *
 * 放开只需把它改成 `false`: 上传、`/api/restore/batch`、逐份结果与打包下载都已就绪。
 */
const RESTORE_WIP = true;

/**
 * 把逐份锚点摊成一张表, key 用几种可能的文件名变体。
 *
 * AI 未必原样交回 `【脱敏版】x.docx` —— 常被存成 `x.docx`, 甚至挪进子目录。所以
 * 原名 / basename / 去【脱敏版】前缀都指向同一份锚点; 服务端也按这几档回查。
 */
function anchorMap(files: ExpectedFile[]): Record<string, Record<string, number>> {
  const map: Record<string, Record<string, number>> = {};
  for (const f of files) {
    const base = f.name.split("/").pop() ?? f.name;
    for (const key of [f.name, base, base.replace("【脱敏版】", ""), `【脱敏版】${base}`]) {
      if (key) map[key] = f.anchors;
    }
  }
  return map;
}

/**
 * 「脱敏 → 交 AI → 还原」的第二步: 把 AI 改好的文件交回来, 填回原文。
 *
 * 从侧栏卡片改成独立的「脱敏还原」抽屉(入口在顶栏「设置」左边): 还原是一次低频动作,
 * 不值得常驻占一栏; 只有产物**可还原**时顶栏按钮才可用(`AnonymizeResp.restorable`) ——
 * 在 L2 把某类型改成 mask/redact/remove 就没有锚点, 给一个按下去必然还原不回来的按钮,
 * 比没有更糟。
 *
 * 一次可以交多份(整批还原), 逐份结果分开报; 一份失败不影响其余。
 *
 * 目前整个入口按 `RESTORE_WIP` 标「开发中」并禁用。
 */
export function RestorePanel({ open, onOpenChange, token, sourceName, expected = [], batch = false }: Props) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RestoreBatchResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  async function run(files: File[]) {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.restoreBatch(files, token, anchorMap(expected)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const pick = (files: FileList | null) => {
    const list = [...(files ?? [])];
    if (list.length) void run(list);
  };
  const picker = (ref: React.RefObject<HTMLInputElement | null>) => {
    if (ref.current) ref.current.value = "";   // 选同一个文件两次也要能重跑
    ref.current?.click();
  };

  const okCount = result?.summary.ok ?? 0;
  const problem = result?.results.filter((r) => r.status === "ok" && (r.missing?.length || r.unknown?.length)) ?? [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-lg! **:data-[slot=sheet-close]:top-5">
        <SheetHeader className="gap-1 border-b px-6 py-5">
          <div className="flex items-center gap-2 pr-8">
            <SheetTitle className="text-lg">脱敏还原</SheetTitle>
            {RESTORE_WIP ? (
              <span className="rounded-sm bg-muted px-1.5 py-px text-[10px] font-medium text-muted-foreground">
                开发中
              </span>
            ) : null}
            <span className="ml-auto text-xs text-muted-foreground">格式与样式原样保留</span>
          </div>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-6">
          <div id="restore" className="text-sm">

      <p className="mb-2.5 text-xs leading-relaxed text-muted-foreground">
        {batch ? "把交给 AI 改好的那一批交回来，锚点会填回原文。" : "把交给 AI 改好的那份文件交回来，锚点会填回原文。"}
        <span className="mt-1 block text-muted-foreground/80">对不上的是：{sourceName}</span>
      </p>

      {/* 两个隐藏入口: 多选文件 / 整个文件夹。文件夹入口只在支持 webkitdirectory 且批次模式时给 */}
      <input
        ref={fileRef}
        type="file"
        className="hidden"
        multiple
        accept={RESTORABLE_EXT.map((e) => `.${e}`).join(",")}
        onChange={(e) => pick(e.target.files)}
      />
      {batch && HAS_FOLDER_PICKER ? (
        <input
          ref={folderRef}
          type="file"
          className="hidden"
          multiple
          // webkitdirectory 是 webkit 前缀属性, React 的 JSX 类型里没有 —— 只能这样塞
          {...DIRECTORY_INPUT_PROPS}
          onChange={(e) => pick(e.target.files)}
        />
      ) : null}

      <div className="flex flex-col gap-1.5">
        <Button
          className="w-full"
          disabled={busy || RESTORE_WIP}
          onClick={() => picker(fileRef)}
          title="选择 AI 改好的文件（可多选；docx / xlsx / csv / txt / md）"
        >
          {busy ? "正在还原…" : RESTORE_WIP ? "选文件还原（开发中）" : batch ? "选文件还原（可多选）" : "选文件还原"}
        </Button>
        {batch && HAS_FOLDER_PICKER ? (
          <Button
            variant="outline"
            className="w-full"
            disabled={busy || RESTORE_WIP}
            onClick={() => picker(folderRef)}
          >
            选文件夹还原…{RESTORE_WIP ? "（开发中）" : ""}
          </Button>
        ) : null}
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground/80">
        {RESTORE_WIP
          ? "这个入口还在开发中，暂时不能用。"
          : "PDF 与图片还原不了：脱敏时命中页已整页栅格化，原文不在文件里了。"}
      </p>

      {error ? <p className="mt-2 text-xs text-destructive">还原失败：{error}</p> : null}

      {result ? (
        <div id="restoreResult" className="mt-3 border-t pt-3">
          <p className="text-[13px] tabular-nums">
            已还原 <span className="font-semibold">{okCount}</span> 份
            {result.summary.error ? `（${result.summary.error} 份失败）` : ""}
          </p>
          {okCount > 1 ? (
            <a
              className="mt-2 block text-xs text-primary underline underline-offset-2"
              href={result.zip_url}
              download
            >
              打包下载（zip · 全部还原件）
            </a>
          ) : null}

          <ul className="mt-2 space-y-1.5">
            {result.results.map((r) => (
              <li key={r.filename} className="text-xs leading-snug">
                {r.status === "ok" ? (
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <a
                      className="text-primary underline underline-offset-2"
                      href={r.output_url}
                      download={r.output_name}
                    >
                      {r.output_name}
                    </a>
                    <span className="tabular-nums text-muted-foreground">已还原 {r.total_restored} 处</span>
                  </span>
                ) : (
                  <span className="text-destructive">{r.filename || "（无名）"}：{r.reason}</span>
                )}
              </li>
            ))}
          </ul>

          <a
            className="mt-2 block text-xs text-muted-foreground underline underline-offset-2"
            href={result.report_url}
            download
          >
            下载对账报告
          </a>

          {problem.map((r) => (
            <div key={r.filename} className="mt-2">
              {r.missing?.length ? (
                <p className="text-xs text-destructive">
                  {r.filename}：有 {r.missing.length} 个锚点在这份文件里没找到（AI 可能删掉或改写了），请人工核对：
                  {r.missing.slice(0, 6).join("、")}
                  {r.missing.length > 6 ? " …" : ""}
                </p>
              ) : null}
              {r.unknown?.length ? (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {r.filename}：有 {r.unknown.length} 个锚点不在映射表里（AI 可能自己编的），已原样保留、未替换：
                  {r.unknown.slice(0, 6).join("、")}
                  {r.unknown.length > 6 ? " …" : ""}
                </p>
              ) : null}
            </div>
          ))}
          {okCount > 0 && problem.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">全部锚点都对上了。</p>
          ) : null}
          </div>
        ) : null}
        </div>
      </div>
      </SheetContent>
    </Sheet>
  );
}
