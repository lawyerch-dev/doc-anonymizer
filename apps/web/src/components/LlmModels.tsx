import { useEffect, useRef, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import * as api from "../lib/api";
import { humanSize } from "../lib/formats";
import type { DownloadState, LlmModelRow } from "../types";

type Props = {
  models: LlmModelRow[];
  /** 选中哪个模型(写进 config 的 llm.model_id); 后端据此把服务起好 */
  modelId: string;
  onChangeModelId: (value: string) => void;
  /** 下载完成后要让上层重取目录, "已安装"标记才会变 */
  onModelsChanged: () => void;
};

/**
 * "用哪个大模型": 点一个就用它 —— 没装的话选中即开始下载, 起服务由后端在开跑前做。
 *
 * 这里**不出现**服务地址、模型别名、启动命令: 那些是实现细节。用户要决定的只有"用哪个模型",
 * 剩下的(起服务、换模型)是 app 的事 —— 把 `serve_llm.sh` 甩给用户复制, 等于没做完。
 */
export function LlmModels({ models, modelId, onChangeModelId, onModelsChanged }: Props) {
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
  const busy = dl?.state === "downloading";
  const pct =
    dl && dl.total_bytes ? Math.min(100, Math.round((dl.done_bytes / dl.total_bytes) * 100)) : null;

  const install = async (id: string) => {
    setErr(null);
    try {
      setDl(await api.startModelDownload(id));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  /** 选中它 = 用它; 还没装就顺手装上, 免得用户还要再点一次 */
  const pick = (m: LlmModelRow) => {
    onChangeModelId(m.id);
    if (!m.downloaded) void install(m.id);
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
      <div className="space-y-1">
        {ordered.map((m) => {
          const on = modelId === m.id;
          const installing = busy && dl?.id === m.id;
          return (
            <label
              key={m.id}
              className="flex cursor-pointer items-start gap-2 rounded-md border border-input px-2 py-1.5 text-xs hover:bg-accent/50"
              title={m.file}
            >
              <input
                type="radio"
                name="llm-model"
                className="mt-0.5"
                checked={on}
                onChange={() => pick(m)}
              />
              <span className="min-w-0">
                <span className={on ? "font-medium" : ""}>
                  {m.name}
                  {m.recommended ? (
                    <span className="ml-1.5 rounded bg-selected/10 px-1 text-[10px] text-selected">
                      推荐
                    </span>
                  ) : null}
                </span>
                <span className="block text-[11px] leading-snug text-muted-foreground">{m.hint}</span>
                <span className="block text-[11px] leading-snug text-muted-foreground">
                  {m.downloaded
                    ? "已安装，可直接用"
                    : installing
                      ? "正在安装…"
                      : `还没安装 · ${m.size_gb} GB（选中就开始下载）`}
                </span>
              </span>
            </label>
          );
        })}
      </div>

      {!modelId ? (
        <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
          没选模型：会用配置里那个"已经跑起来的服务"。选一个模型就改由本机托管。
        </p>
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
                <span className="text-muted-foreground">中断了也没事，再点会接着下</span>
                <Button variant="ghost" size="xs" onClick={() => void cancel()}>
                  取消
                </Button>
              </div>
            </>
          ) : dl?.state === "cancelled" ? (
            <p className="text-muted-foreground">已取消。已下的部分留着，选中它会接着下。</p>
          ) : (
            <p className="text-destructive">下载失败：{dl?.error}</p>
          )}
        </div>
      ) : null}

      {err ? <p className="mt-1 text-[11px] text-destructive">{err}</p> : null}
    </div>
  );
}
