import { useRef } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import type { Preset, UploadResp } from "../types";

/** 还没选文件时的三步引导(窄栏里放不下长文案, 只给动作词) */
const STEPS = ["上传文件", "点击一键脱敏", "检查效果"];

type Props = {
  presets: Preset[];
  /** 本次会话上传过的文件: 与示例同列 —— 上传完就该在列表里看见"我选了什么" */
  uploads: UploadResp[];
  /** 当前选中的文档名(示例与上传件同名同法比较) */
  activeName: string | null;
  loading: boolean;
  // 是否已经点过「加载示例」: 区分"还没加载"(给引导文案)与"加载过但 samples/ 是空的"
  loaded: boolean;
  onPick: (preset: Preset) => void;
  onPickUpload: (upload: UploadResp) => void;
  onRefresh: () => void;
  onUpload: (file: File) => void;
  uploading: boolean;
};

export function PresetList({
  presets, uploads, activeName, loading, loaded, onPick, onPickUpload, onRefresh, onUpload, uploading,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

  // 上传件排在示例前面(刚上传的就是要看的那份), 行样式与选中态完全一致, 只有来源标签不同:
  // 示例看扩展名, 上传件写"已上传"。两类合成一张表, 免得同一套行标记写两遍。
  const rows = [
    ...uploads.map((u) => ({
      key: u.token, cls: "upload", name: u.filename, tag: "已上传", pick: () => onPickUpload(u),
    })),
    ...presets.map((p) => ({
      key: p.name, cls: "preset", name: p.name, tag: p.name.split(".").pop() ?? "", pick: () => onPick(p),
    })),
  ];

  return (
    <div className="flex min-h-56 flex-1 flex-col rounded-xl border bg-card p-3.5">
      <div className="mb-2.5 flex flex-none items-center justify-between">
        <h3 className="text-[13px] font-semibold tracking-wide text-muted-foreground">选择文档</h3>
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

      <input
        ref={fileRef}
        type="file"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onUpload(f);
          e.target.value = "";
        }}
      />
      <Button
        className="mb-2.5 w-full flex-none"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
      >
        {uploading ? "上传中…" : "上传本地文件…"}
      </Button>

      {loading ? (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">加载中…</div>
      ) : rows.length ? (
        <div className="scroll-thin min-h-0 flex-1 overflow-auto overscroll-contain">
          {rows.map((row) => {
            const active = row.name === activeName;
            return (
              // 真 <button>: 之前是 `div role="button"` —— 键盘 Enter/Space、焦点环、
              // 屏幕阅读器都的"能按"语义都得自己补, 用原生元素则自带(.preset 这个类名保留给 E2E)
              <button
                key={row.key}
                type="button"
                aria-pressed={active}
                className={`${row.cls} mb-1.5 flex w-full cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-[13px] transition-colors ${
                  active
                    ? "border-selected bg-selected font-semibold text-selected-foreground shadow-sm"
                    : "hover:border-primary/60 hover:bg-accent/60"
                }`}
                title={row.name}
                onClick={row.pick}
              >
                <span aria-hidden>📄</span>
                <span className="min-w-0 flex-1 truncate">{row.name}</span>
                <span className={`text-[11px] uppercase ${active ? "text-selected-foreground/80" : "text-muted-foreground"}`}>
                  {row.tag}
                </span>
              </button>
            );
          })}
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
    </div>
  );
}
