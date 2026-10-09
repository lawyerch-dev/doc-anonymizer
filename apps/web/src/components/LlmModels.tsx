import { useEffect, useRef, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import * as api from "../lib/api";
import { humanSize } from "../lib/formats";
import type { DownloadState, LlmModelRow } from "../types";

type Props = {
  models: LlmModelRow[];
  /** 已跑起来的那个服务的地址与别名(不是文件路径) */
  baseUrl: string;
  model: string;
  onChangeBaseUrl: (value: string) => void;
  onChangeModel: (value: string) => void;
  /** 下载完成后要让上层重取目录, "已下载"标记才会变 */
  onModelsChanged: () => void;
};

/**
 * "用哪个大模型": 目录里挑一个, 没下就下, 下好了给出起服务的命令。
 *
 * **选了模型不改「模型名」**: 那个字段是 llama-server 的 `--alias`(`scripts/serve_llm.sh` 固定用
 * `qwen3.8-4b`), 不是 gguf 文件名。把别名写成文件名会让"用别名启动的服务"对不上 —— 所以这里
 * 只讲清"该用哪个文件、怎么起服务", 不替用户猜别名, 地址与模型名留在下面的"自定义服务"里。
 */
export function LlmModels({
  models, baseUrl, model, onChangeBaseUrl, onChangeModel, onModelsChanged,
}: Props) {
  const [picked, setPicked] = useState<string | null>(null);
  const [dl, setDl] = useState<DownloadState | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // 回调放进 ref: 上层若传内联函数, 每渲染都会变, 会让下面的轮询 effect 反复重建
  const notifyRef = useRef(onModelsChanged);
  notifyRef.current = onModelsChanged;
  const seenDone = useRef<string | null>(null);

  // 轮询下载进度。只在本组件挂着时轮(弹窗关掉就停); 后端不受影响, 重开能查到进度。
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.modelDownloadStatus();
        if (!alive) return;
        setDl(s);
        if (s.state === "done" && s.id && seenDone.current !== s.id) {
          seenDone.current = s.id;   // 每个任务只通知一次, 否则会反复重取目录
          notifyRef.current();
        }
      } catch {
        // 拉不到状态就保持上一次显示, 不打断界面(下一次轮询会纠正)
      }
    };
    void tick();
    const every = dl?.state === "downloading" ? 1000 : 5000;
    const timer = window.setInterval(() => void tick(), every);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [dl?.state]);

  const ordered = [...models].sort((a, b) => Number(b.recommended) - Number(a.recommended));
  const pickedRow = ordered.find((m) => m.id === picked) ?? null;
  const busy = dl?.state === "downloading";
  const pct =
    dl && dl.total_bytes ? Math.min(100, Math.round((dl.done_bytes / dl.total_bytes) * 100)) : null;

  const startDownload = async (id: string) => {
    setErr(null);
    try {
      setDl(await api.startModelDownload(id));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const cancel = async () => {
    try {
      setDl(await api.cancelModelDownload());
    } catch {
      // 取消失败不提示: 下一次轮询会给出真实状态
    }
  };

  return (
    <div className="mb-3">
      <div className="mb-1 text-xs text-muted-foreground">用哪个大模型</div>
      {ordered.length ? (
        <div className="space-y-1">
          {ordered.map((m) => (
            <label
              key={m.id}
              className="flex cursor-pointer items-start gap-2 rounded-md border border-input px-2 py-1.5 text-xs hover:bg-accent/50"
              title={m.file}
            >
              <input
                type="radio"
                name="llm-model"
                className="mt-0.5"
                checked={picked === m.id}
                onChange={() => setPicked(m.id)}
              />
              <span className="min-w-0">
                <span className="font-medium">
                  {m.name}
                  {m.recommended ? (
                    <span className="ml-1.5 rounded bg-selected/10 px-1 text-[10px] text-selected">
                      推荐
                    </span>
                  ) : null}
                </span>
                <span className="block text-[11px] leading-snug text-muted-foreground">{m.hint}</span>
                <span className="block text-[11px] leading-snug text-muted-foreground">
                  {m.downloaded ? "已下载，可直接用" : `还没下载 · ${m.size_gb} GB`}
                </span>
              </span>
            </label>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">模型目录读不到（后端会说明原因）</p>
      )}

      {pickedRow ? (
        <div className="mt-1.5 rounded-md border border-input bg-muted/30 px-2 py-1.5">
          {pickedRow.downloaded ? (
            <>
              <p className="text-[11px] text-muted-foreground">在终端里起服务（复制这一行）:</p>
              <code className="mt-0.5 block text-[11px] break-all">
                ./scripts/serve_llm.sh 8080 var/models/{pickedRow.file}
              </code>
            </>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="xs" disabled={busy} onClick={() => void startDownload(pickedRow.id)}>
                下载（{pickedRow.size_gb} GB）
              </Button>
              <span className="text-[11px] text-muted-foreground">下完再回来，这里会变成启动命令</span>
            </div>
          )}
        </div>
      ) : null}

      {busy || dl?.state === "cancelled" || dl?.state === "error" ? (
        <div className="mt-1.5 rounded-md border border-input px-2 py-1.5 text-[11px]">
          {busy ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <span>正在下载…</span>
                <span className="tabular-nums">
                  {humanSize(dl?.done_bytes ?? 0)}
                  {dl?.total_bytes ? ` / ${humanSize(dl.total_bytes)}（${pct}%）` : ""}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-muted">
                <div
                  className="h-full bg-selected transition-[width] duration-200"
                  style={{ width: `${pct ?? 0}%` }}
                />
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <span className="text-muted-foreground">中断了也没事，再点下载会接着下</span>
                <Button variant="ghost" size="xs" onClick={() => void cancel()}>
                  取消
                </Button>
              </div>
            </>
          ) : dl?.state === "cancelled" ? (
            <p className="text-muted-foreground">已取消。已下的部分留着，再点下载会接着下。</p>
          ) : (
            <p className="text-destructive">下载失败：{dl?.error}</p>
          )}
        </div>
      ) : null}

      {err ? <p className="mt-1 text-[11px] text-destructive">{err}</p> : null}

      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-muted-foreground">自定义服务（高级）</summary>
        <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmUrl">
          服务地址
        </Label>
        <Input
          id="llmUrl"
          className="mt-1 h-8"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="http://127.0.0.1:8080/v1"
          value={baseUrl}
          onChange={(e) => onChangeBaseUrl(e.target.value)}
        />
        <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmModel">
          模型名
        </Label>
        <Input
          id="llmModel"
          className="mt-1 h-8"
          autoComplete="off"
          spellCheck={false}
          value={model}
          onChange={(e) => onChangeModel(e.target.value)}
        />
        <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
          这两项说的是"已经跑起来的那个服务"：地址，以及它启动时用的别名（默认服务是 qwen3.8-4b）。
        </p>
      </details>

      <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
        服务没起来时，脱敏会在开始前报错并告诉你原因，不会静默跳过这一层。
      </p>
    </div>
  );
}
