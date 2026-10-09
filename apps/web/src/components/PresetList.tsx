import { useRef } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import type { Preset } from "../types";

type Props = {
  presets: Preset[];
  activeName: string | null;
  loading: boolean;
  onPick: (preset: Preset) => void;
  onRefresh: () => void;
  onUpload: (file: File) => void;
  uploading: boolean;
};

export function PresetList({ presets, activeName, loading, onPick, onRefresh, onUpload, uploading }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-xl border bg-card p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold tracking-wide text-muted-foreground">选择文档</h3>
        <Button variant="ghost" size="xs" onClick={onRefresh} disabled={loading} title="重新加载 samples/ 里的示例">
          ↻ 刷新示例
        </Button>
      </div>

      {loading ? (
        <div className="text-xs text-muted-foreground">加载中…</div>
      ) : presets.length ? (
        <div className="max-h-56 overflow-auto">
          {presets.map((p) => {
            const active = p.name === activeName;
            return (
              <div
                key={p.name}
                className={`preset mb-1.5 flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-[13px] transition-colors ${
                  active ? "border-primary bg-accent font-semibold text-accent-foreground" : "hover:border-primary/60 hover:bg-accent/60"
                }`}
                title={p.name}
                onClick={() => onPick(p)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onPick(p); }}
              >
                <span aria-hidden>📄</span>
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                <span className="ml-auto text-[11px] uppercase text-muted-foreground">
                  {p.name.split(".").pop()}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">samples/ 无可预览示例</div>
      )}

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
        variant="outline"
        size="sm"
        className="mt-2 w-full"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
      >
        {uploading ? "上传中…" : "上传本地文件…"}
      </Button>
    </div>
  );
}
