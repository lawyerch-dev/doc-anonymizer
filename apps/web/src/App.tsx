import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { ConfigPanel } from "./components/ConfigPanel";
import { LogModal } from "./components/LogModal";
import { PresetList } from "./components/PresetList";
import { Preview } from "./components/Preview";
import { SettingsSheet } from "./components/SettingsSheet";
import { StatsCard } from "./components/StatsCard";
import * as api from "./lib/api";
import { DEFAULT_SCHEME, progressInfo } from "./lib/formats";
import type { AnonymizeResp, ConfigData, ConfigRow, LlmModelRow, Preset, ProgressState, Selection } from "./types";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  const saved = localStorage.getItem("docanon.theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const [configs, setConfigs] = useState<ConfigRow[]>([]);
  const [configRef, setConfigRef] = useState<string | null>(null);
  const [configData, setConfigData] = useState<ConfigData | null>(null);
  const [configKind, setConfigKind] = useState<"builtin" | "user" | null>(null);
  const [configDirty, setConfigDirty] = useState(false);
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  // 正在跑的 job id: 取消按钮要知道叫停谁
  const runningJob = useRef<string | null>(null);

  // 暗色: 顶层加 .dark(theme.css 的 dark 变体就挂在这个 class 上)
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("docanon.theme", theme);
  }, [theme]);

  // 设置里改了东西没保存就刷新/关页 → 让浏览器确认一次, 否则改动静默丢掉
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
      setPresets(await api.loadPresets());
      setError(null);
    } catch (e) {
      setError(`示例加载失败: ${(e as Error).message}`);
    } finally {
      setPresetsLoading(false);
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
      const rows = await api.loadConfigs();
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

  // 模型目录(ONNX 可选 + 可下载的大模型)。下载完成后要重取一次, "已下载"标记才会变。
  const refreshModels = useCallback(() => {
    api.loadModels()
      .then((m) => { setModelDirs(m.onnx_dirs); setLlmModels(m.llm_models); })
      .catch(() => { setModelDirs([]); setLlmModels([]); });
  }, []);

  useEffect(() => { void refreshPresets(); }, [refreshPresets]);
  useEffect(() => { void loadConfigList(); }, [loadConfigList]);
  useEffect(() => { refreshModels(); }, [refreshModels]);

  const pickPreset = (p: Preset) => {
    setSelection({ preset: p.name, token: null, filename: p.name, url: p.url });
    setResult(null);
    setError(null);
    setDrawerOpen(false);
  };

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const up = await api.uploadFile(file);
      setSelection({ preset: null, token: up.token, filename: up.filename, url: up.url });
      setResult(null);
      setError(null);
      setDrawerOpen(false);
    } catch (e) {
      setError(`上传失败: ${(e as Error).message}`);
    } finally {
      setUploading(false);
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
      // 未编辑 → 发口径名(日志显示真实口径); 编辑过 → 发内联对象
      if (configData && configDirty) payload.config = configData;
      else if (configRef) payload.config = configRef;

      const resp = await api.anonymize(payload);
      setResult(resp);
      setLogOpen(false);
    } catch (e) {
      const msg = (e as Error).message;
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

  const saveConfig = async () => {
    if (!configData) return;
    const suggested = configRef && !configRef.endsWith(".yaml") ? configRef : "my-config";
    const name = window.prompt("配置名（字母/数字/下划线/连字符）:", suggested);
    if (!name) return;
    try {
      await api.saveConfig(name, configData);
      localStorage.setItem("docanon.config", name);
      await loadConfigList();
    } catch (e) {
      setError(`保存失败: ${(e as Error).message}`);
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

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-baseline gap-3 border-b bg-card px-6 py-3">
        <h1 className="text-lg font-semibold">文档脱敏工具</h1>
        <span className="text-[13px] text-muted-foreground">选文档 → 预览 → 一键脱敏 → 原格式前后对比</span>
        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant="ghost" size="xs"
            onClick={() => setSettingsOpen(true)}
            title={`脱敏设置：口径、逐类型策略、检测引擎（当前口径：${configRef ?? "未加载"}）`}
          >
            ⚙ 设置{configDirty ? " •" : ""}
          </Button>
          <Button
            variant="ghost" size="xs"
            disabled={!result?.trace}
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
          className={`min-h-0 w-[280px] flex-none space-y-3 overflow-auto overscroll-contain md:block ${
            drawerOpen
              ? "fixed inset-y-0 left-0 z-40 w-[300px] bg-background p-4 shadow-xl md:static md:w-[280px] md:bg-transparent md:p-0 md:shadow-none"
              : "hidden"
          }`}
        >
          <PresetList
            presets={presets}
            activeName={selection?.preset ?? null}
            loading={presetsLoading}
            uploading={uploading}
            onPick={pickPreset}
            onRefresh={() => void refreshPresets()}
            onUpload={(f) => void upload(f)}
          />
          <Button id="run" className="w-full" disabled={!selection || running} onClick={() => void run()}>
            {running ? "脱敏中…" : "开始脱敏"}
          </Button>
          {/* 最准档跑一份合同要 30+ 秒: 只说"脱敏中…"用户会以为卡死了 —— 给出阶段、进度、已用秒数, 并允许取消 */}
          {running ? (
            <div className="space-y-1.5" id="progress">
              <p className="text-xs leading-snug text-foreground/80">{runInfo.label}</p>
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
              totalMs={result.trace?.timing?.total_ms ?? null}
              convertedFrom={result.trace?.converted_from ?? null}
            />
          ) : null}
        </aside>

        {/* 窄屏唤起抽屉的按钮(抽屉里只有选文档) */}
        <Button variant="outline" size="sm" className="md:hidden" onClick={() => setDrawerOpen(true)}>
          选择文档
        </Button>

        <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-2">
          <Preview
            pane="src" title="原文" placeholder="左侧选择或上传一个文档"
            filename={selection?.filename ?? ""} url={selection?.url ?? ""}
            action={selection ? { label: "下载原件", href: selection.url } : undefined}
          />
          <Preview
            pane="out" title="脱敏后" placeholder="点击「开始脱敏」查看结果"
            filename={result?.output_name ?? ""} url={result?.output_url ?? ""}
            action={result ? { label: "下载脱敏件", href: result.output_url } : undefined}
          />
        </main>
      </div>

      <SettingsSheet open={settingsOpen} onOpenChange={setSettingsOpen}>
        <ConfigPanel
          configs={configs}
          configRef={configRef}
          configData={configData}
          configKind={configKind}
          modelDirs={modelDirs}
          llmModels={llmModels}
          onSelectConfig={(name) => void loadConfigData(name)}
          onChange={(next) => { setConfigData(next); setConfigDirty(true); }}
          onModelsChanged={refreshModels}
          onSave={() => void saveConfig()}
          onImport={(f) => void importConfig(f)}
          onExport={() => { if (configRef) location.href = api.exportConfigUrl(configRef); }}
        />
      </SettingsSheet>

      <LogModal open={logOpen} trace={result?.trace ?? null} onClose={() => setLogOpen(false)} />
    </div>
  );
}
