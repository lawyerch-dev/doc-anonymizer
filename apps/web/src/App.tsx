import { useCallback, useEffect, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { ConfigPanel } from "./components/ConfigPanel";
import { LogModal } from "./components/LogModal";
import { PresetList } from "./components/PresetList";
import { Preview } from "./components/Preview";
import { SettingsSheet } from "./components/SettingsSheet";
import { StatsCard } from "./components/StatsCard";
import * as api from "./lib/api";
import type { AnonymizeResp, ConfigData, ConfigRow, LlmModelRow, Preset, Selection } from "./types";

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
  const [error, setError] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 暗色: 顶层加 .dark(theme.css 的 dark 变体就挂在这个 class 上)
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("docanon.theme", theme);
  }, [theme]);

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
      const pick = rows.find((c) => c.name === saved) ?? rows.find((c) => c.current) ?? rows[0];
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
    try {
      const payload: { preset?: string; token?: string; config?: string | ConfigData } = {};
      if (selection.preset) payload.preset = selection.preset;
      else if (selection.token) payload.token = selection.token;
      // 未编辑 → 发口径名(日志显示真实口径); 编辑过 → 发内联对象
      if (configData && configDirty) payload.config = configData;
      else if (configRef) payload.config = configRef;

      const resp = await api.anonymize(payload);
      setResult(resp);
      setLogOpen(false);
    } catch (e) {
      setError(`脱敏失败: ${(e as Error).message}`);
    } finally {
      setRunning(false);
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
        {/* 左栏: 宽屏常驻; 窄屏收成抽屉 */}
        <aside
          className={`min-h-0 w-[280px] flex-none space-y-3 overflow-auto overscroll-contain md:block ${
            drawerOpen ? "fixed inset-y-0 left-0 z-40 w-[300px] bg-background p-4 shadow-xl" : "hidden"
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
