import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { ConfigPanel } from "./components/ConfigPanel";
import { LogModal } from "./components/LogModal";
import { Logo } from "./components/Logo";
import { OnboardingWizard, clearOnboarding, hasDoneOnboarding } from "./components/OnboardingWizard";
import { PresetList } from "./components/PresetList";
import { Preview } from "./components/Preview";
import { RestorePanel } from "./components/RestorePanel";
import { SettingsSheet } from "./components/SettingsSheet";
import { StatsCard } from "./components/StatsCard";
import { UploadPrefsPanel } from "./components/UploadPrefsPanel";
import * as api from "./lib/api";
import { DEFAULT_SCHEME, progressInfo, shadowNameOf, shadowState, visibleSchemes } from "./lib/formats";
import {
  defaultUploadPrefs, uploadRuleSummary, type UploadPrefs,
} from "./lib/uploadPrefs";
import type {
  AnonymizeResp, BatchSummary, ConfigData, ConfigRow, DocRow, LlmModelRow, Preset, ProgressState,
  Selection, UploadResp,
} from "./types";

/**
 * 署名与版本进**窗口标题栏**（桌面上由壳设原生标题，浏览器里就是这个 document.title）。
 * 界面正文里不重复显示 —— 原来那条底部信息条已按反馈移除（不够明显）。
 */
const APP_TITLE = "文档脱敏工具 — 陈恒律师 自用";

type Theme = "light" | "dark";

/** 一批的上限, 与后端 `routes.BATCH_MAX_FILES`/`BATCH_MAX_BYTES` 对齐（前端先拦一道给出人话） */
const FOLDER_MAX_FILES = 300;
const FOLDER_MAX_BYTES = 500 * 1024 * 1024;
/** 单文件上限, 与后端 `routes._MAX_BYTES` 对齐 */
const MAX_FILE_BYTES = 50 * 1024 * 1024;

/**
 * 选文件夹时整层跳过的目录(隐藏目录如 `.git`/`.venv` 由"隐藏项"那条规则一起挡掉)。
 * 选到代码仓库/工程目录时, 这些里面是依赖与构建产物, 不是案子材料。
 */
const BLOCKED_DIRS = new Set([
  "node_modules", "dist", "build", "target", "out", "vendor", "coverage",
  "__pycache__", "site-packages", "bower_components", "Pods", "DerivedData",
]);

/**
 * 选文件夹靠 `<input webkitdirectory>`。它在 Safari/Chromium 上都有, 但**WKWebView(桌面壳)未必放行** --
 * 探测一次: 没有这个属性就不显示入口, 而不是点了一下什么都不发生。
 */
const HAS_FOLDER_PICKER =
  typeof HTMLInputElement !== "undefined" && "webkitdirectory" in HTMLInputElement.prototype;

const extOf = (name: string) => (name.includes(".") ? `.${name.split(".").pop()!.toLowerCase()}` : "");

function presetRows(presets: Preset[]): DocRow[] {
  return presets.map((p) => ({
    key: `preset:${p.name}`,
    name: p.name,
    tag: p.name.split(".").pop() ?? "",
    kind: "preset",
    status: "idle",
    ref: { preset: p.name, token: null, filename: p.name, url: p.url },
  }));
}

function uploadRows(uploads: UploadResp[]): DocRow[] {
  return uploads.map((u) => ({
    key: `upload:${u.token}`,
    name: u.filename,
    tag: "已上传",
    kind: "upload",
    status: "idle",
    ref: { preset: null, token: u.token, filename: u.filename, url: u.url },
  }));
}

function initialTheme(): Theme {
  const saved = localStorage.getItem("docanon.theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  // 示例**不自动加载**(启动时不读 samples/, 只在上方「加载示例」被点过之后才有内容)
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [presetsLoaded, setPresetsLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  /** 上传进度(选文件夹时逐份传, 得让人看见"传到第几份") */
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
  /** 界面上能认出哪些类型: 从 /api/formats 拿(后端抽取器注册表), 前端不硬编码 */
  const [formats, setFormats] = useState<string[]>([]);
  /** 收件规则(收哪些类型 / 要不要连子文件夹): 设置里可编辑, 存在后端(见下面的读取 effect) */
  const [uploadPrefs, setUploadPrefs] = useState<UploadPrefs>(defaultUploadPrefs);
  /** 上一批跳过了什么(只计数): "不进列表"与"装作没有"是两回事 */
  const [skipNote, setSkipNote] = useState<string | null>(null);

  /** 列表的两种来源(互斥): 单份(示例/上传) 或 一个文件夹批次 */
  const [mode, setMode] = useState<"single" | "folder">("single");
  const [rows, setRows] = useState<DocRow[]>([]);
  const [batchRows, setBatchRows] = useState<DocRow[]>([]);
  const [batch, setBatch] = useState<{ id: string; folder: string; zipUrl: string; mappingUrl: string } | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const [configs, setConfigs] = useState<ConfigRow[]>([]);
  const [configRef, setConfigRef] = useState<string | null>(null);
  const [configData, setConfigData] = useState<ConfigData | null>(null);
  const [configKind, setConfigKind] = useState<"builtin" | "user" | null>(null);
  const [configDirty, setConfigDirty] = useState(false);
  /** 自动保存的状态: 设置里给一行字看("正在保存…/已自动保存/保存失败") */
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [modelDirs, setModelDirs] = useState<string[]>([]);
  const [llmModels, setLlmModels] = useState<LlmModelRow[]>([]);

  const [selection, setSelection] = useState<Selection | null>(null);
  const [result, setResult] = useState<AnonymizeResp | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<ProgressState | null>(null);
  // 跑起来的时刻: 用来显示"已用 N 秒"(轮询每 600ms 触发一次重渲染, 秒数跟着走)
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  /** 「上传文件」那节在设置里默认展不展开: 从左栏「改」进来就展开, 从顶栏「设置」进来就收起 */
  const [uploadOpen, setUploadOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // 首次使用向导: 本地记"看过了", 看过一次就不再弹; 设置里可手动叫回来
  const [showIntro, setShowIntro] = useState(() => !hasDoneOnboarding());
  // 版本号从后端 /health 读(单一真相在 pyproject/__version__): 前端写死一份迟早跟包版本漂移
  const [version, setVersion] = useState<string | null>(null);
  // 正在跑的 job id: 取消按钮要知道叫停谁
  const runningJob = useRef<string | null>(null);
  // 日志弹窗关掉后焦点要回到这个按钮, 否则键盘用户被扔到页面开头(组件库的默认回收依赖"点击时按钮已聚焦")
  const logBtnRef = useRef<HTMLButtonElement>(null);
  // 上次选的文件夹里的文件清单: 勾/取消"也收图片与纯文本"时按新规则重筛, 不用再选一次目录
  const lastPicked = useRef<File[]>([]);

  const visibleRows = mode === "folder" ? batchRows : rows;
  const activeRow = visibleRows.find((r) => r.key === activeKey) ?? null;
  // 用布尔量而不是到处 `mode === "folder"`: 在 JSX 的某个分支里 mode 已被收窄, 再比较会被 TS 判成恒假
  const folderMode = mode === "folder";
  // 一键脱敏只在"有东西可跑"时出现: 单份模式要选中一份, 文件夹模式要有至少一份能跑的
  const canRun = folderMode
    ? batchRows.some((r) => r.status !== "unsupported")
    : rows.length > 0 || selection !== null;

  // 暗色: 顶层加 .dark(theme.css 的 dark 变体就挂在这个 class 上)
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("docanon.theme", theme);
  }, [theme]);

  // 设置里改了还没落盘(在自动保存的防抖窗口里, 或存盘失败) → 让浏览器确认一次, 否则改动丢掉
  useEffect(() => {
    if (!configDirty) return;
    const onLeave = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [configDirty]);

  const refreshPresets = useCallback(async () => {
    setPresetsLoading(true);
    try {
      const list = await api.loadPresets();
      // 示例行与上传行拼成单份列表(上传件在前 —— 刚传的就是要看的那份)
      setRows((prev) => [...prev.filter((r) => r.kind === "upload"), ...presetRows(list)]);
      setError(null);
    } catch (e) {
      setError(`示例加载失败: ${(e as Error).message}`);
    } finally {
      setPresetsLoading(false);
      setPresetsLoaded(true);
    }
  }, []);

  const loadConfigData = useCallback(async (ref: string) => {
    try {
      const detail = await api.loadConfigData(ref);
      setConfigRef(ref);
      setConfigData(detail.data);
      setConfigKind(detail.kind);
      setConfigDirty(false);
      localStorage.setItem("docanon.config", ref);
      setError(null);
    } catch (e) {
      setConfigRef(null);
      setConfigData(null);
      setConfigKind(null);
      setError(`读取配置失败: ${(e as Error).message}`);
    }
  }, []);

  const loadConfigList = useCallback(async () => {
    try {
      // 展示层裁掉不暴露的方案(legal.yaml): 后端列表不变, 但界面只在三套里选,
      // 否则默认值/下拉会出现"列表里没有这个值"的坏状态
      const rows = visibleSchemes(await api.loadConfigs());
      setConfigs(rows);
      setError(null);
      const saved = localStorage.getItem("docanon.config");
      // 记忆 > 界面默认那套 > 后端启动时用的那套 > 列表第一项
      const pick = rows.find((c) => c.name === saved)
        ?? rows.find((c) => c.name === DEFAULT_SCHEME)
        ?? rows.find((c) => c.current)
        ?? rows[0];
      if (pick) await loadConfigData(pick.name);
    } catch (e) {
      setError(`配置列表加载失败: ${(e as Error).message}`);
    }
  }, [loadConfigData]);

  // ---- 自动保存: 设置里改完就存, 不用点保存 ----
  // 内置三套是只读的(configs/*.yaml), 所以改动落在**同名影子**里(改 `onnx.yaml` → 存
  // `var/configs/onnx.yaml`)。影子不进方案下拉: 界面上还是那三套, 只是标一句"已改",
  // 并给一个「恢复默认」把影子清掉。防抖 800ms: 连打词表/拖下拉时别把 PUT 打成一串。
  const pending = useRef<ConfigData | null>(null);
  const saveTimer = useRef<number | null>(null);

  /** 丢掉还没落盘的改动(恢复默认/换方案要重来时用) */
  const cancelPending = () => {
    if (saveTimer.current !== null) {
      window.clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    pending.current = null;
  };

  const persist = useCallback(async (data: ConfigData) => {
    // 已经在用户配置上(影子/导入的那份) → 原地覆盖; 还在内置上 → 落到它的影子
    const target = configKind === "user" && configRef
      ? configRef
      : shadowNameOf(configRef ?? DEFAULT_SCHEME);
    setSaveState("saving");
    try {
      await api.saveConfig(target, data);
      localStorage.setItem("docanon.config", target);
      setConfigDirty(false);
      setSaveError(null);
      setSaveState("saved");
      // 刚立起影子: 当前口径要切到它(否则跑的仍是那份只读的内置), 列表也要重取, 影子才查得到
      if (target !== configRef) await loadConfigList();
    } catch (e) {
      setSaveState("error");
      setSaveError((e as Error).message);
    }
  }, [configRef, configKind, loadConfigList]);

  /** 把还没落盘的改动立刻存掉(换方案前调一次, 别把刚改的那步丢掉) */
  const flushSave = useCallback(async () => {
    if (saveTimer.current !== null) {
      window.clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    const data = pending.current;
    if (!data) return;
    pending.current = null;
    await persist(data);
  }, [persist]);

  const changeConfig = (next: ConfigData) => {
    setConfigData(next);
    setConfigDirty(true);
    cancelPending();
    pending.current = next;
    saveTimer.current = window.setTimeout(() => void flushSave(), 800);
  };

  /**
   * 换方案: 先把改动落盘再换, 否则防抖窗口里那次改动会跟着旧方案一起丢掉。
   * 选的是内置那套时若已有影子(你改过它), 就接着用影子 —— 换一圈回来改动还在。
   */
  const switchConfig = async (name: string) => {
    await flushSave();
    setSaveState("idle");
    const shadow = shadowNameOf(name);
    const customized = configs.some((c) => c.kind === "user" && c.name === shadow);
    await loadConfigData(customized ? shadow : name);
  };

  /** 一键恢复默认: 清掉所有影子(你改过的方案都在里面), 回到出厂那套 */
  const resetConfig = async () => {
    cancelPending();
    setSaveState("idle");
    const { shadows } = shadowState(configs);
    for (const name of shadows) {
      try {
        await api.deleteConfig(name);
      } catch {
        // 删不掉就留着: 下一次改动照旧能覆盖它, 不该因为清理失败挡住"继续用"
      }
    }
    localStorage.setItem("docanon.config", DEFAULT_SCHEME);
    await loadConfigList();
  };

  // 模型目录(ONNX 可选 + 可下载的大模型)。下载完成后要重取一次, "已下载"标记才会变。
  const refreshModels = useCallback(() => {
    api.loadModels()
      .then((m) => { setModelDirs(m.onnx_dirs); setLlmModels(m.llm_models); })
      .catch(() => { setModelDirs([]); setLlmModels([]); });
  }, []);

  useEffect(() => { void loadConfigList(); }, [loadConfigList]);
  useEffect(() => { refreshModels(); }, [refreshModels]);
  // 收件规则存在后端(`/api/settings`): 打包成 .app 后换机器、清 WebView 数据都不会丢。
  // 后端没存过就没有这一段, 保持界面默认值; 拉不到也只是回到默认, 不该因此让整个界面不可用。
  useEffect(() => {
    api.loadSettings()
      .then((s) => { if (s.upload) setUploadPrefs(s.upload); })
      .catch(() => {});
  }, []);
  useEffect(() => {
    api.loadHealth().then((h) => setVersion(h.version)).catch(() => {});
    // 类型清单拿不到就不预过滤(照样能跑, 只是不在选文件夹时提示"X 个不支持")
    api.loadFormats().then(setFormats).catch(() => setFormats([]));
  }, []);

  // 版本号一到就写进标题栏。与桌面壳设的那个原生标题是同一句 —— 谁生效都对。
  useEffect(() => {
    document.title = version ? `${APP_TITLE} · v${version}` : APP_TITLE;
  }, [version]);

  /**
   * 选中一份文档。
   * **已处理好的** → 右栏给正常的脱敏前后对比; **还没处理好的**（待跑/跑中/未处理/失败）→
   * 右栏显示它的状态与原因, 而不是一片空白对比。
   */
  const pickRow = (row: DocRow) => {
    setSelection(row.ref);
    setActiveKey(row.key);
    setResult(row.status === "ok" && row.outputUrl
      ? { output_name: row.outputName ?? "", output_url: row.outputUrl, counts: row.counts ?? {}, kind: "" }
      : null);
    setError(null);
    setDrawerOpen(false);
  };

  const upload = async (files: File[]) => {
    setUploading(true);
    setSkipNote(null); // 那行计数属于文件夹批次, 切回单份就别留着了
    try {
      for (const [i, file] of files.entries()) {
        const up = await api.uploadFile(file);
        const row = uploadRows([up])[0];
        // 同名重传就换掉旧的那条, 列表里不留两份一样的
        setRows((prev) => [row, ...prev.filter((r) => !(r.kind === "upload" && r.name === up.filename))]);
        pickRow(row);
        if (files.length > 1) setUploadProgress({ done: i + 1, total: files.length });
      }
      setMode("single");
    } catch (e) {
      setError(`上传失败: ${(e as Error).message}`);
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  };

  /**
   * 选一个文件夹 = 一个批次: 逐份上传(保留相对目录), 然后一次跑完。
   *
   * 收件规则与"要不要连子文件夹"来自设置(`uploadPrefs`, 默认**收办公文档与图片 + 只收这一层**)。
   * 实测反馈: 选错一个代码仓库时, 里面成百上千个 `.md`/`.txt`/`.png`(子目录里更多)也是
   * "能读的类型", 会被当成待脱敏文档全捞进来。
   *
   * 没进的按四类**计数**并写在列表上方: 子文件夹里的、非收件类型、依赖/构建目录、隐藏项 ——
   * 不进列表, 但也绝不装作没有("静默少一层"那条边界)。
   */
  const pickFolder = async (files: File[], prefs: UploadPrefs = uploadPrefs) => {
    lastPicked.current = files;
    const relOf = (f: File) => (f.webkitRelativePath || f.name).split("/").slice(1).join("/") || f.name;
    const folder = (files[0]?.webkitRelativePath || "").split("/")[0] || "文件夹";
    // 规则可能与后端的能力清单不一致(改过配置/后端升过级): 以两边都认的为准; 清单没拿到就信规则
    const allowed = new Set(
      formats.length ? prefs.extensions.filter((e) => formats.includes(e)) : prefs.extensions,
    );

    let hidden = 0;
    let nested = 0;
    let blocked = 0;
    const picked: { file: File; relpath: string }[] = [];
    for (const f of files) {
      const relpath = relOf(f);
      const parts = relpath.split("/");
      if (parts.some((p) => p.startsWith("."))) { hidden += 1; continue; }
      if (parts.length > 1 && !prefs.recursive) { nested += 1; continue; }
      if (parts.slice(0, -1).some((p) => BLOCKED_DIRS.has(p))) { blocked += 1; continue; }
      picked.push({ file: f, relpath });
    }

    const keep: typeof picked = [];
    const skipped: typeof picked = [];
    for (const x of picked) {
      (allowed.has(extOf(x.file.name)) ? keep : skipped).push(x);
    }
    const todo = keep.filter((x) => x.file.size <= MAX_FILE_BYTES);
    const tooBig = keep.filter((x) => x.file.size > MAX_FILE_BYTES);

    const byExt = new Map<string, number>();
    for (const x of skipped) {
      const e = extOf(x.file.name) || "无扩展名";
      byExt.set(e, (byExt.get(e) ?? 0) + 1);
    }
    const top = [...byExt.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);
    const rest = skipped.length - top.reduce((n, [, c]) => n + c, 0);
    const notes: string[] = [];
    if (nested) notes.push(`子文件夹里 ${nested} 个未收（设置里可打开「遍历子文件夹」）`);
    if (skipped.length) {
      notes.push(
        `已跳过 ${skipped.length} 个非收件类型（${top.map(([e, c]) => `${e} ${c}`).join(" · ")}` +
        `${rest ? ` 等 ${rest} 个` : ""}）`,
      );
    }
    if (blocked) notes.push(`依赖/构建目录 ${blocked} 个`);
    if (hidden) notes.push(`隐藏项 ${hidden} 个`);
    setSkipNote(notes.length ? notes.join(" · ") : null);

    const id = `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    const row = (x: { file: File; relpath: string }, status: DocRow["status"], reason?: string): DocRow => ({
      key: `${id}:${x.relpath}`,
      name: x.relpath,
      tag: "文件夹",
      kind: "batch",
      status,
      reason,
      ref: {
        preset: null, token: id, filename: x.relpath,
        url: status === "idle" ? `/uploads/${id}/${x.relpath}` : "",
      },
    });

    if (todo.length > FOLDER_MAX_FILES || todo.reduce((n, x) => n + x.file.size, 0) > FOLDER_MAX_BYTES) {
      setError(`一次最多 ${FOLDER_MAX_FILES} 份 / 500MB（这次 ${todo.length} 份），分两批跑`);
      return;
    }

    // 能跑的 + 超 50MB 的(要让人看见是哪几个)进列表; 其余只在上面那行计数里露面
    setBatchRows([...todo.map((x) => row(x, "idle")), ...tooBig.map((x) => row(x, "unsupported", "超过 50MB 上限"))]);
    setBatch({ id, folder, zipUrl: "", mappingUrl: "" });
    setBatchSummary(null);
    setMode("folder");
    setSelection(null);
    setActiveKey(null);
    setResult(null);
    setError(todo.length || tooBig.length
      ? null
      : nested && !prefs.recursive
        ? "这个文件夹里没有可脱敏的文档 —— 文档都在子文件夹里，设置里可打开「遍历子文件夹」"
        : "这个文件夹里没有收件规则内的文档 —— 在 设置 → 上传文件 里可改收件规则");
    if (!todo.length) return;

    setUploading(true);
    setUploadProgress({ done: 0, total: todo.length });
    const failed = new Map<string, string>();
    for (const [i, x] of todo.entries()) {
      try {
        await api.uploadFile(x.file, { id, relpath: x.relpath });
      } catch (e) {
        failed.set(x.relpath, (e as Error).message);
      }
      setUploadProgress({ done: i + 1, total: todo.length });
    }
    setUploading(false);
    setUploadProgress(null);
    if (failed.size) {
      // 没传上去的不能留在"待跑": 标成失败并把原因说清楚
      setBatchRows((prev) => prev.map((r) => failed.has(r.name)
        ? { ...r, status: "error", reason: `上传失败：${failed.get(r.name)}` }
        : r));
    }
  };

  /**
   * 改收件规则(设置里): 存到后端, 并且**按手上那个文件夹的清单立刻重筛** ——
   * 那份文件的清单还留着, 不用再选一次目录。
   */
  const changeUploadPrefs = (next: UploadPrefs) => {
    setUploadPrefs(next);
    // 存不上也不打断这一批: 界面已按新规则重筛, 下次改动会再试一次
    api.saveSettings({ upload: next }).catch(() => {});
    if (mode === "folder" && lastPicked.current.length) void pickFolder(lastPicked.current, next);
  };

  const configPayload = (): { config?: string | ConfigData } => {
    // 未编辑 → 发口径名(日志显示真实口径); 编辑过 → 发内联对象
    if (configData && configDirty) return { config: configData };
    if (configRef) return { config: configRef };
    return {};
  };

  /** 跑批次: 一个 job, 进度按"第 i/N 份"走; 取消时已完成的那几份是完整产物, 照旧给出来 */
  const runBatch = async () => {
    if (!batch) return;
    const t0 = Date.now();
    const job = `job-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    runningJob.current = job;
    setRunning(true);
    setError(null);
    setProgress(null);
    setStartedAt(t0);
    const poll = window.setInterval(() => {
      api.runProgress(job).then(setProgress).catch(() => {});
    }, 600);
    setBatchRows((prev) => prev.map((r) => (r.status === "idle" ? { ...r, status: "running" } : r)));
    try {
      const resp = await api.anonymizeBatch({ batch: batch.id, job, ...configPayload() });
      const bySource = new Map(resp.results.map((r) => [r.source, r]));
      const nextRows = batchRows.map((r) => {
        const hit = bySource.get(r.name);
        // 后端没提到这一份 = 它压根没上传(预过滤掉的), 状态本来就是对的; 只有还挂着"跑中"的要放回去
        if (!hit) return r.status === "running" ? { ...r, status: "idle" as const } : r;
        return hit.status === "ok"
          ? {
              ...r, status: "ok" as const, counts: hit.counts,
              outputName: hit.output_name, outputUrl: hit.output_url,
              restorable: hit.restorable, anchors: hit.anchors, reason: undefined,
            }
          : { ...r, status: hit.status, reason: hit.reason };
      });
      setBatchRows(nextRows);
      setBatch((b) => (b ? { ...b, zipUrl: resp.zip_url, mappingUrl: resp.mapping_url } : b));
      // 汇总按**列表**算, 不用后端的 summary: 客户端预过滤掉的(类型不支持/超 50MB/没传上去的)不在后端账上,
      // 按后端算会得出"2 份"，而用户眼前明明有 3 行 —— 那是两套数字打架。
      setBatchSummary({
        total: nextRows.length,
        ok: nextRows.filter((r) => r.status === "ok").length,
        unsupported: nextRows.filter((r) => r.status === "unsupported").length,
        error: nextRows.filter((r) => r.status === "error").length,
      });
      // 批次: 还原面板用的是**选中那一行**的 anchors(一批共用一份 mapping, 逐份不同)。
      // 所以这里只带批次 token, anchors 从 activeRow 取 —— 见下面 RestorePanel 的接线。
      const anyRestorable = nextRows.some((r) => r.restorable);
      setResult({
        output_name: "",
        output_url: "",
        kind: "",
        restorable: anyRestorable,
        restore_token: resp.restore_token ?? null,
        counts: resp.results.reduce<Record<string, number>>((acc, r) => {
          for (const [k, v] of Object.entries(r.counts ?? {})) acc[k] = (acc[k] ?? 0) + v;
          return acc;
        }, {}),
        trace: { source: batch.folder, extractor: "", detectors: [], timing: { total_ms: Date.now() - t0 }, detections: [] },
      });
      if (resp.batch.cancelled) {
        setError(`已取消：这批跑完 ${resp.summary.ok + resp.summary.unsupported + resp.summary.error}/${resp.summary.total} 份，已完成的产物在上面。`);
      }
    } catch (e) {
      const msg = (e as Error).message;
      setBatchRows((prev) => prev.map((r) => (r.status === "running" ? { ...r, status: "idle" } : r)));
      setError(msg.includes("已取消") ? null : `脱敏失败: ${msg}`);
    } finally {
      window.clearInterval(poll);
      setProgress(null);
      setStartedAt(null);
      runningJob.current = null;
      setRunning(false);
    }
  };

  const run = async () => {
    if (!selection) return;
    setRunning(true);
    setError(null);
    setProgress(null);
    setStartedAt(Date.now());
    // job id 只用来读进度/叫停(不带鉴权含义); 生成得够随机就行
    const job = `job-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    runningJob.current = job;
    const poll = window.setInterval(() => {
      api.runProgress(job).then(setProgress).catch(() => {});
    }, 600);
    try {
      const payload: { preset?: string; token?: string; config?: string | ConfigData; job?: string } = { job };
      if (selection.preset) payload.preset = selection.preset;
      else if (selection.token) payload.token = selection.token;
      Object.assign(payload, configPayload());

      const resp = await api.anonymize(payload);
      setResult(resp);
      // 这一行标记成"已处理", 与批次里的行同一套状态(点回去才有对比看)
      setRows((prev) => prev.map((r) => (r.key === activeKey
        ? { ...r, status: "ok", counts: resp.counts, outputName: resp.output_name, outputUrl: resp.output_url, reason: undefined }
        : r)));
      setLogOpen(false);
    } catch (e) {
      const msg = (e as Error).message;
      setRows((prev) => prev.map((r) => (r.key === activeKey ? { ...r, status: "error", reason: msg } : r)));
      // 用户自己按的取消: 不该当成"脱敏失败"弹红条
      setError(msg.includes("已取消") ? null : `脱敏失败: ${msg}`);
    } finally {
      window.clearInterval(poll);
      setProgress(null);
      setStartedAt(null);
      runningJob.current = null;
      setRunning(false);
    }
  };

  const cancelRun = async () => {
    const job = runningJob.current;
    if (!job) return;
    try {
      await api.cancelAnonymize(job);
    } catch {
      // 取消失败不提示: 请求跑完了就会自己收尾
    }
  };

  const importConfig = async (file: File) => {
    try {
      await api.importConfig(file);
      await loadConfigList();
    } catch (e) {
      setError(`导入失败: ${(e as Error).message}`);
    }
  };

  const runInfo = progressInfo(progress);
  const elapsed = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
  const batchTimeMs = result?.trace?.timing?.total_ms ?? null;

  /** 右栏(脱敏后)该显示什么: 已处理好的给对比, 没处理好的给它的状态 */
  const outPlaceholder = !activeRow
    ? (mode === "folder" ? "点一份看它的前后对比，或先点「一键脱敏」跑完这批" : "点击「一键脱敏」查看结果")
    : activeRow.status === "ok"
      ? "正在加载脱敏件…"
      : activeRow.status === "running"
        ? `正在处理：${runInfo.label}`
        : activeRow.status === "unsupported"
          ? `未处理：${activeRow.reason ?? "该类型暂不支持"}`
          : activeRow.status === "error"
            ? `失败：${activeRow.reason ?? "未知原因"}`
            : "还没跑 —— 点「一键脱敏」";
  /** 左栏(原文)同理: 没传上去的那份没有原文可看, 原因写在原地 */
  const srcPlaceholder = !activeRow
    ? "左侧选择上传文档"
    : `未上传：${activeRow.reason ?? "这份没有可预览的原文"}`;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-baseline gap-3 border-b bg-card px-6 py-3">
        <Logo className="size-6 flex-none self-center" />
        <h1 className="text-lg font-semibold">文档脱敏工具</h1>
        <span className="text-[13px] tabular-nums text-muted-foreground">
          {version ? `v${version} · ` : ""}@陈恒律师自研自用
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="ghost" size="xs"
            onClick={() => { setUploadOpen(false); setSettingsOpen(true); }}
            title={`设置：上传收件规则与脱敏方案（方案 / 脱敏规则 / 识别方式）（当前口径：${configRef ?? "未加载"}）`}
          >
            ⚙ 设置{configDirty ? " •" : ""}
          </Button>
          <Button
            ref={logBtnRef}
            variant="ghost" size="xs"
            disabled={mode === "folder" || !result?.trace?.detections?.length}
            onClick={() => setLogOpen(true)}
          >
            运行日志
          </Button>
          <Button
            variant="ghost" size="xs"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title="切换明暗"
          >
            {theme === "dark" ? "☀ 浅色" : "🌙 深色"}
          </Button>
        </div>
      </header>

      {showIntro ? (
        /* 首次使用向导: 选个方案就能用(本地记"看过了"不再弹); 选中即切到当前配置 */
        <OnboardingWizard
          key="intro"
          configs={configs}
          currentConfig={configRef}
          onPickConfig={(name) => { void switchConfig(name); }}
          onModelsChanged={refreshModels}
          onDone={() => setShowIntro(false)}
        />
      ) : null}

      {error ? (
        // role=alert: 出错时屏幕阅读器要念出来, 不然"点了没反应"对看不见的人是零信息
        <div
          role="alert"
          className="mx-6 mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          {error}
        </div>
      ) : null}

      {/* 窄屏抽屉的遮罩: 点空白关掉 —— 否则抽屉盖住半屏又没有出口, 只能靠"选一个文档"隐式消失 */}
      {drawerOpen ? (
        <div
          className="fixed inset-0 z-30 bg-black/20 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden
        />
      ) : null}

      <div className="flex min-h-0 flex-1 gap-4 p-4">
        {/* 左栏: 宽屏常驻; 窄屏收成抽屉。
            抽屉打开时若把窗口拉宽到 md, 这些 fixed/宽度/阴影要被 md: 前缀收回常态 ——
            否则会留一个盖住半屏、又(因为按钮 md:hidden)没有出口的固定层 */}
        <aside
          className={`flex min-h-0 w-[280px] flex-none flex-col gap-3 overflow-auto overscroll-contain md:flex ${
            drawerOpen
              ? "fixed inset-y-0 left-0 z-40 w-[300px] bg-background p-4 shadow-xl md:static md:w-[280px] md:bg-transparent md:p-0 md:shadow-none"
              : "hidden"
          }`}
        >
          <PresetList
            rows={visibleRows}
            activeKey={activeKey}
            loading={presetsLoading}
            loaded={presetsLoaded}
            uploading={uploading}
            uploadProgress={uploadProgress}
            folderName={mode === "folder" ? batch?.folder ?? "文件夹" : null}
            hasFolderPicker={HAS_FOLDER_PICKER}
            ruleSummary={uploadRuleSummary(uploadPrefs, formats)}
            onEditRule={() => { setUploadOpen(true); setSettingsOpen(true); }}
            skipNote={mode === "folder" ? skipNote : null}
            onPick={pickRow}
            onPickFolder={(files) => void pickFolder(files)}
            onExitFolder={() => {
              setMode("single");
              setSelection(null);
              setActiveKey(null);
              setResult(null);
              setSkipNote(null);
            }}
            onRefresh={() => void refreshPresets()}
            onUpload={(files) => void upload(files)}
          />
          {canRun ? (
            <Button
              id="run"
              className="w-full"
              disabled={running || (!folderMode && !selection)}
              onClick={() => void (folderMode ? runBatch() : run())}
            >
              {running ? "脱敏中…" : folderMode ? `一键脱敏（${batchRows.length} 份）` : "一键脱敏"}
            </Button>
          ) : null}
          {/* 整包取走: 只含脱敏件; 映射表含原文, 单独一个口子并说明风险。
              用 outline 而不是再来一个实心主按钮 —— 与「一键脱敏」并排时两个黑块看着像一对开关 */}
          {batch?.zipUrl ? (
            <a
              id="downloadZip"
              href={`${batch.zipUrl}?name=${encodeURIComponent(batch.folder)}`}
              download
              className="inline-flex w-full flex-none items-center justify-center rounded-lg border px-2.5 py-2 text-sm font-medium hover:bg-muted"
            >
              打包下载（zip）
            </a>
          ) : null}
          {batch?.mappingUrl ? (
            <a
              href={batch.mappingUrl}
              download
              title="映射表含原文, 切勿与脱敏件一起外发"
              className="flex-none text-center text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              下载映射表（含原文，勿外发）
            </a>
          ) : null}
          {/* 最准档跑一份合同要 30+ 秒: 只说"脱敏中…"用户会以为卡死了 —— 给出阶段、进度、已用秒数, 并允许取消 */}
          {running ? (
            <div className="space-y-1.5" id="progress">
              <p className="text-xs leading-snug text-foreground/80">{runInfo.label}</p>
              {progress?.file ? (
                <p className="truncate text-[11px] leading-snug text-muted-foreground" title={progress.file}>
                  {progress.file}
                </p>
              ) : null}
              {runInfo.pct !== null ? (
                <div className="h-1.5 w-full overflow-hidden rounded bg-muted">
                  <div
                    className="h-full bg-selected transition-[width] duration-300"
                    style={{ width: `${runInfo.pct}%` }}
                  />
                </div>
              ) : null}
              <p className="text-[11px] tabular-nums leading-snug text-muted-foreground">
                已用 {elapsed}s
              </p>
              {/* 8 秒还没完才解释 —— 快的档不该看到这句废话 */}
              {elapsed >= 8 ? (
                <p className="text-[11px] leading-snug text-muted-foreground">
                  还在跑（本地大模型档跑长文档通常 30-60 秒），不想等可以取消。
                </p>
              ) : null}
              <Button
                id="cancelRun"
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => void cancelRun()}
              >
                取消
              </Button>
            </div>
          ) : null}
          {/* 这个按钮只可能在抽屉打开时可见(关着时 aside 整体 hidden), 所以只会有"收起"一个态 */}
          <Button
            variant="outline" size="sm" className="w-full md:hidden"
            onClick={() => setDrawerOpen(false)}
          >
            收起面板
          </Button>
          {result ? (
            <StatsCard
              counts={result.counts}
              total={api.totalCounts(result.counts)}
              totalMs={batchTimeMs}
              convertedFrom={result.trace?.converted_from ?? null}
              summary={mode === "folder" ? batchSummary : null}
            />
          ) : null}
          {/* 还原入口只在产物可还原时出现。默认三套口径都出锚点, 所以正常都有;
              只有在 L2 把某类型改成了 mask/redact/remove 才没有锚点, 按下去也变不回来。
              批次模式带上**这一批逐份的锚点**: 一批共用一份 mapping, 逐份的锚点不同,
              拿批次合计去对账会把别的文件的锚点误报成缺失。 */}
          {result?.restorable && result.restore_token ? (
            <RestorePanel
              token={result.restore_token}
              batch={folderMode}
              sourceName={folderMode ? batch?.folder ?? "这一批" : result.output_name}
              expected={
                folderMode
                  ? batchRows
                      .filter((r) => r.status === "ok" && r.anchors && Object.keys(r.anchors).length > 0)
                      .map((r) => ({ name: r.outputName ?? r.name, anchors: r.anchors! }))
                  : result.anchors
                    ? [{ name: result.output_name, anchors: result.anchors }]
                    : []
              }
            />
          ) : null}
        </aside>

        {/* 窄屏唤起抽屉的按钮(抽屉里只有选文档) */}
        <Button variant="outline" size="sm" className="md:hidden" onClick={() => setDrawerOpen(true)}>
          选择文档
        </Button>

        <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-2">
          <Preview
            pane="src" title="原文" placeholder={srcPlaceholder}
            filename={selection?.filename ?? ""} url={selection?.url ?? ""}
            action={selection?.url ? { label: "下载原件", href: selection.url } : undefined}
          />
          <Preview
            pane="out" title="脱敏后" placeholder={outPlaceholder}
            filename={result?.output_name ?? ""} url={result?.output_url ?? ""}
            action={result?.output_url ? { label: "下载脱敏件", href: result.output_url } : undefined}
          />
        </main>
      </div>

      <SettingsSheet
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        saveState={saveState}
        saveError={saveError}
        canReset={shadowState(configs).shadows.size > 0}
        onReset={() => void resetConfig()}
        onReplayIntro={() => {
          clearOnboarding();
          setSettingsOpen(false);
          setShowIntro(true);
        }}
      >
        {/* 上传收件规则放最上面: 左栏那个「改」跳到这儿, 一眼就能看到(下面才是脱敏方案与策略) */}
        <UploadPrefsPanel
          formats={formats}
          prefs={uploadPrefs}
          onChange={changeUploadPrefs}
          defaultOpen={uploadOpen}
        />
        <div className="my-3 border-t" />
        <ConfigPanel
          configs={configs}
          configRef={configRef}
          configData={configData}
          configKind={configKind}
          modelDirs={modelDirs}
          llmModels={llmModels}
          onSelectConfig={(name) => void switchConfig(name)}
          onChange={changeConfig}
          onModelsChanged={refreshModels}
          onImport={(f) => void importConfig(f)}
          onExport={() => { if (configRef) location.href = api.exportConfigUrl(configRef); }}
        />
      </SettingsSheet>

      <LogModal
        open={logOpen}
        trace={result?.trace ?? null}
        onClose={() => setLogOpen(false)}
        returnFocusTo={logBtnRef}
      />
    </div>
  );
}
