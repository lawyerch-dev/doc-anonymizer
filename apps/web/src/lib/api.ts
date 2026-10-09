import type {
  AnonymizeResp, ConfigData, ConfigDetail, ConfigRow, Detection, ModelsResp, Preset, UploadResp,
} from "../types";

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, { cache: "no-store", ...init });
  const body = (await resp.json()) as T & { error?: string };
  if (body && typeof body === "object" && "error" in body && body.error) {
    throw new Error(body.error);
  }
  return body;
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

export const uploadFile = (file: File) =>
  fileToBase64(file).then((content_b64) =>
    postJson<UploadResp>("/api/upload", { filename: file.name, content_b64 }),
  );

export const anonymize = (payload: {
  preset?: string; token?: string; config?: string | ConfigData;
}) => postJson<AnonymizeResp>("/api/anonymize", payload);

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

export type { Detection };
