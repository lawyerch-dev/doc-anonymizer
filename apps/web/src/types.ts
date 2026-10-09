export type Preset = { name: string; url: string; size: number; preview: boolean };

export type ConfigRow = {
  name: string;
  label: string;
  kind: "builtin" | "user";
  current?: boolean;
};

export type Detection = {
  entity_type: string;
  source: string;
  strategy: string;
  original: string;
  replacement?: string;
  locator: Record<string, unknown>;
};

export type Trace = {
  source: string;
  extractor: string;
  converted_from?: string | null;
  config?: string;
  detectors: string[];
  timing: Record<string, number>;
  detections: Detection[];
};

export type AnonymizeResp = {
  output_name: string;
  output_url: string;
  counts: Record<string, number>;
  kind: string;
  trace?: Trace;
};

export type UploadResp = { token: string; filename: string; url: string };

export type ConfigData = {
  strategies: Record<string, string>;
  detectors: Record<string, boolean>;
  dictionary?: string[];
  onnx?: { model_dirs?: string[] };
  llm?: { base_url?: string; model?: string };
};

export type ConfigDetail = { ref: string; kind: "builtin" | "user"; data: ConfigData };

export type ModelsResp = {
  onnx_dirs: string[];
  llm: { base_url: string; model: string };
};

export type Selection = {
  preset: string | null;
  token: string | null;
  filename: string;
  url: string;
};
