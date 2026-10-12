export type Preset = { name: string; url: string; size: number; preview: boolean };

export type ConfigRow = {
  name: string;
  label: string;
  /** 配置首行注释里的一句话说明(什么时候用它); 用户自存的配置通常没有 */
  hint: string;
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
  llm?: { base_url?: string; model?: string; model_id?: string };
};

export type ConfigDetail = { ref: string; kind: "builtin" | "user"; data: ConfigData };

export type ModelsResp = {
  onnx_dirs: string[];
  llm: { base_url: string; model: string };
  /** 可下载的大模型目录(configs/llm_models.yaml) + 是否已下载 */
  llm_models: LlmModelRow[];
  /** 托管服务的状态(选了模型后由后端自己起) */
  llm_server?: LlmServerState;
};

/** 后端托管的 llama-server 状态 */
export type LlmServerState = {
  state: "idle" | "running" | "error";
  model_id: string;
  port: number;
  error: string;
};

/** 跑一份文档时的进度(前端按 job id 轮询 `/api/progress/<job>`) */
export type ProgressState = {
  stage: "extract" | "detect" | "write" | "done" | "unknown";
  done: number;
  total: number;
  cancelled: boolean;
  /** 批次专用: 正在跑哪一份 / 第几份 / 共几份(单份流程一直是空/0) */
  file?: string;
  index?: number;
  total_files?: number;
};

export type LlmModelRow = {
  id: string;
  name: string;
  hint: string;
  repo: string;
  file: string;
  size_gb: number;
  recommended: boolean;
  downloaded: boolean;
};

/** 后端下载任务的状态(进程内单例, 一次一个) */
export type DownloadState = {
  id: string | null;
  state: "idle" | "downloading" | "done" | "error" | "cancelled";
  done_bytes: number;
  total_bytes: number | null;
  error: string | null;
};

export type Selection = {
  preset: string | null;
  token: string | null;
  filename: string;
  url: string;
};

/** 列表里每一行的状态: "已处理好的看对比, 没处理好的显示状态"就靠它 */
export type DocStatus = "idle" | "running" | "ok" | "unsupported" | "error";

/**
 * 「选择文档」列表里的一行: 示例 / 单份上传 / 文件夹批次里的一份 —— 同一套渲染, 差在来源与状态。
 * `ref` 就是"选中它要用的东西"(与 `Selection` 同形), 点行后直接拿它去预览/跑。
 */
export type DocRow = {
  key: string;
  /** 显示名(批次里是相对路径, 保留层级才看得出文件夹结构) */
  name: string;
  /** 来源标签: 示例看扩展名, 单份上传写"已上传", 文件夹来的写"文件夹" */
  tag: string;
  kind: "preset" | "upload" | "batch";
  status: DocStatus;
  counts?: Record<string, number>;
  outputName?: string;
  outputUrl?: string;
  /** 未处理/失败的原因(状态徽标的悬停提示也用它) */
  reason?: string;
  ref: Selection;
};

/** 批次里一份的结果 */
export type BatchFileResult = {
  source: string;
  status: "ok" | "unsupported" | "error";
  output_name?: string;
  output_url?: string;
  counts?: Record<string, number>;
  reason?: string;
};

export type BatchSummary = { total: number; ok: number; unsupported: number; error: number };

/** `/api/anonymize{batch}` 的响应 */
export type AnonymizeBatchResp = {
  batch: { cancelled: boolean; total: number };
  summary: BatchSummary;
  results: BatchFileResult[];
  mapping_url: string;
  zip_url: string;
};

/** `/health`: 桌面壳拿 pid 认自己的后端; 界面拿 version 显示版本号(唯一真相在后端) */
export type Health = { ok: boolean; pid: number; version: string };

/**
 * 首次"初始化"的进度(按方案在后台补齐所需资源)。
 * 只有状态与字节数 —— 模型名/镜像/文件数这些是实现细节, 界面不显示。
 */
export type PrepareState = {
  state: "idle" | "running" | "done" | "error" | "cancelled";
  done_bytes: number;
  total_bytes: number | null;
  error: string | null;
};
