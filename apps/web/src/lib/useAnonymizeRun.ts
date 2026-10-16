import { useCallback, useRef, useState } from "react";
import * as api from "./api";
import { newId } from "./ids";
import type { ProgressState } from "../types";

/**
 * 一次脱敏运行的**外壳**: 生成 job、起进度轮询、跑完(成功或失败)统一收尾清理。
 *
 * 单份(`run`)与批量(`runBatch`)之前把这套生命周期各写了一遍(同一段 setRunning/progress/
 * `setInterval`/finally), 改一处漏一处。这里只收"外壳" —— 各自收到响应后怎么落到自己的行/汇总上
 * 确实不同, 留在调用方。
 *
 * `task(job)` 抛出的错误交给 `onError`, 由调用方决定回滚哪些行、怎么显示横幅。
 * `clearError` 在开跑前调用(通常就是 `setError(null)`), 让调用方保留错误的单一归属。
 */
export function useAnonymizeRun(clearError?: () => void) {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const runningJob = useRef<string | null>(null);

  const run = useCallback(
    async (task: (job: string) => Promise<void>, onError: (e: Error) => void) => {
      const job = newId("job");
      runningJob.current = job;
      clearError?.();
      setRunning(true);
      setProgress(null);
      setStartedAt(Date.now());
      // 同步请求没有流, 只能按 job 短轮询"到哪一步了"
      const poll = window.setInterval(() => {
        api.runProgress(job).then(setProgress).catch(() => {});
      }, 600);
      try {
        await task(job);
      } catch (e) {
        onError(e as Error);
      } finally {
        window.clearInterval(poll);
        setProgress(null);
        setStartedAt(null);
        runningJob.current = null;
        setRunning(false);
      }
    },
    [clearError],
  );

  const cancel = useCallback(async () => {
    const job = runningJob.current;
    if (!job) return;
    try {
      await api.cancelAnonymize(job);
    } catch {
      // 取消失败不提示: 请求跑完了就会自己收尾
    }
  }, []);

  return { running, progress, startedAt, run, cancel };
}
