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
  /**
   * 这份产物能不能还原(产物里有没有可寻址锚点)。
   * 内置三套默认全类型 anchor, 所以正常是 true; 为 false 时界面**不给**还原入口 ——
   * 在 L2 把某类型改成了 mask/redact/remove 才会出现这种情况, 替换值里已经没有原文了,
   * 给一个按下去必然还原不回来的按钮, 比没有更糟。
   */
  restorable?: boolean;
  /** 这份文件里的锚点 → 次数。还原时随请求带上, 后端据此报"少了哪些"。 */
  anchors?: Record<string, number>;
  /** 哪一次脱敏的产物目录(还原时凭它指回服务端的 mapping.json) */
  restore_token?: string | null;
  trace?: Trace;
};

/** `/api/restore` 的响应: 还原件 + 对账结果 */
export type RestoreResp = {
  output_name: string;
  output_url: string;
  report_url: string;
  restored: Record<string, number>;
  total_restored: number;
  /** 文中有、映射表里没有 —— AI 编的, 已原样保留未替换 */
  unknown: string[];
  /** 该文件本该有、文里没有 —— AI 删了或改坏了 */
  missing: string[];
  complete: boolean;
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
  /** 这一份能不能还原 / 它该有哪些锚点(批次里逐份不同 —— 一批共用一份 mapping) */
  restorable?: boolean;
  anchors?: Record<string, number>;
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
  /** 这份能不能还原(见 `AnonymizeResp.restorable`) */
  restorable?: boolean;
  /** 逐份的锚点 —— 一批共用一份 mapping, 还原时要靠它区分"这份该有哪些锚点" */
  anchors?: Record<string, number>;
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
  restore_token?: string;
};

/** 批量还原里一份的结果(成功给下载地址, 失败给原因 —— 一份失败不拖垮整批) */
export type RestoreBatchItem = {
  filename: string;
  status: "ok" | "error";
  output_name?: string;
  output_url?: string;
  total_restored?: number;
  unknown?: string[];
  missing?: string[];
  complete?: boolean;
  reason?: string;
};

/** `/api/restore/batch` 的响应: 逐份结果 + 汇总 + 打包下载 */
export type RestoreBatchResp = {
  results: RestoreBatchItem[];
  summary: { total: number; ok: number; error: number };
  zip_url: string;
  report_url: string;
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
