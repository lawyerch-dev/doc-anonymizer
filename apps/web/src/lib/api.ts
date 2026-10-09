import type {
  AnonymizeResp, ConfigData, ConfigDetail, ConfigRow, Detection, DownloadState, LlmModelRow,
  ModelsResp, Preset, ProgressState, UploadResp,
} from "../types";

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, { cache: "no-store", ...init });
  const body = (await resp.json()) as T & { error?: string };
  if (body && typeof body === "object" && "error" in body && body.error) {
    throw new Error(body.error);
  }
  return body;
}

/**
 * 同 `json`, 但**不把 `error` 当请求失败**。
 *
 * 下载状态本身就带一个 `error` 字段(那是**任务**的失败原因)。若走 `json()`, 这个字段会被当成
 * "请求失败"抛掉, 于是失败原因永远到不了界面 —— 正是"静默少一层"。所以状态类接口用这个。
 */
async function plainJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, { cache: "no-store", ...init });
  return (await resp.json()) as T;
}

const postJson = <T>(url: string, payload: unknown) =>
  json<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const loadPresets = () =>
  json<{ presets: Preset[] }>("/api/presets").then((r) => r.presets);

export const loadConfigs = () =>
  json<{ configs: ConfigRow[] }>("/api/configs").then((r) => r.configs);

export const loadConfigData = (ref: string) =>
  json<ConfigDetail>(`/api/configs/${encodeURIComponent(ref)}`);

export const loadModels = () => json<ModelsResp>("/api/models");

export const startModelDownload = (id: string) =>
  postJson<DownloadState>("/api/models/download", { id });

// 状态与取消用 plainJson: 它们的响应里 `error` 是"任务为什么失败", 不是"这次请求失败"
export const modelDownloadStatus = () => plainJson<DownloadState>("/api/models/download");

export const cancelModelDownload = () =>
  plainJson<DownloadState>("/api/models/download/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

export const uploadFile = (file: File) =>
  fileToBase64(file).then((content_b64) =>
    postJson<UploadResp>("/api/upload", { filename: file.name, content_b64 }),
  );

export const anonymize = (payload: {
  preset?: string; token?: string; config?: string | ConfigData; job?: string;
}) => postJson<AnonymizeResp>("/api/anonymize", payload);

/** 跑的时候按 job id 读进度(轮询, 不占那条正在跑的请求) */
export const runProgress = (job: string) =>
  plainJson<ProgressState>(`/api/progress/${encodeURIComponent(job)}`);

/** 叫停正在跑的那一份; 后端在写产物之前查信号, 所以取消 = 不留半成品 */
export const cancelAnonymize = (job: string) =>
  plainJson<{ cancelled: boolean }>("/api/anonymize/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job }),
  });

export const saveConfig = (name: string, data: ConfigData) =>
  json<{ saved: boolean; name: string }>(`/api/configs/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const importConfig = (file: File) =>
  fileToBase64(file).then((content_b64) =>
    postJson<{ name: string }>("/api/configs/import", { filename: file.name, content_b64 }),
  );

export const exportConfigUrl = (ref: string) =>
  `/api/configs/${encodeURIComponent(ref)}/export`;

/** File → base64(分块, 避免大文件把栈打爆; 与旧 app.js 同一策略) */
export async function fileToBase64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  let s = "";
  for (let i = 0; i < buf.length; i += 0x8000) {
    s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  }
  return btoa(s);
}

export function totalCounts(counts: Record<string, number> | undefined): number {
  return Object.values(counts ?? {}).reduce((a, b) => a + b, 0);
}

export type { Detection, LlmModelRow };
