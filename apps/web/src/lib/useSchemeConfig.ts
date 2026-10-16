import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { DEFAULT_SCHEME, shadowNameOf, shadowState, visibleSchemes } from "./formats";
import type { ConfigData, ConfigRow, LlmModelRow } from "../types";

/**
 * 方案配置的全部状态与动作: 方案列表 / 当前方案 / 「影子」自动保存 / 模型目录。
 *
 * 之前在 App 根堆了 9 个 state + 8 个 handler, 这几件事自成一体(读列表 → 选一套 → 改完防抖落"影子"
 * → 换方案前先落盘 → 一键恢复默认), 抽出来让根组件只留"用"它们的 JSX。
 *
 * `notifyError` 用来报"读/存失败" —— 错误的归属仍留在 App(与其它错误共用同一条横幅)。
 *
 * 影子: 内置三套(`configs/*.yaml`)是只读的, 改动落在**同名用户配置**里(改 `onnx.yaml` →
 * `var/configs/onnx.yaml`); 影子不进方案下拉, 只标一句"已改"。
 */
export function useSchemeConfig(notifyError: (msg: string | null) => void) {
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

  // 改动还没落盘(在防抖窗口里, 或存盘失败) → 让浏览器确认一次, 否则改动丢掉
  useEffect(() => {
    if (!configDirty) return;
    const onLeave = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [configDirty]);

  const loadConfigData = useCallback(async (ref: string) => {
    try {
      const detail = await api.loadConfigData(ref);
      setConfigRef(ref);
      setConfigData(detail.data);
      setConfigKind(detail.kind);
      setConfigDirty(false);
      localStorage.setItem("docanon.config", ref);
      notifyError(null);
    } catch (e) {
      setConfigRef(null);
      setConfigData(null);
      setConfigKind(null);
      notifyError(`读取配置失败: ${(e as Error).message}`);
    }
  }, [notifyError]);

  const loadConfigList = useCallback(async () => {
    try {
      // 展示层裁掉不暴露的方案(legal.yaml): 后端列表不变, 但界面只在三套里选,
      // 否则默认值/下拉会出现"列表里没有这个值"的坏状态
      const rows = visibleSchemes(await api.loadConfigs());
      setConfigs(rows);
      notifyError(null);
      const saved = localStorage.getItem("docanon.config");
      // 记忆 > 界面默认那套 > 后端启动时用的那套 > 列表第一项
      const pick = rows.find((c) => c.name === saved)
        ?? rows.find((c) => c.name === DEFAULT_SCHEME)
        ?? rows.find((c) => c.current)
        ?? rows[0];
      if (pick) await loadConfigData(pick.name);
    } catch (e) {
      notifyError(`配置列表加载失败: ${(e as Error).message}`);
    }
  }, [loadConfigData, notifyError]);

  // ---- 自动保存(防抖 800ms: 连打词表/拖下拉时别把 PUT 打成一串) ----
  const pending = useRef<ConfigData | null>(null);
  const saveTimer = useRef<number | null>(null);

  /** 丢掉还没落盘的改动(恢复默认/换方案要重来时用) */
  const cancelPending = useCallback(() => {
    if (saveTimer.current !== null) {
      window.clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    pending.current = null;
  }, []);

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

  const changeConfig = useCallback((next: ConfigData) => {
    setConfigData(next);
    setConfigDirty(true);
    cancelPending();
    pending.current = next;
    saveTimer.current = window.setTimeout(() => void flushSave(), 800);
  }, [cancelPending, flushSave]);

  /**
   * 换方案: 先把改动落盘再换, 否则防抖窗口里那次改动会跟着旧方案一起丢掉。
   * 选的是内置那套时若已有影子(你改过它), 就接着用影子 —— 换一圈回来改动还在。
   */
  const switchConfig = useCallback(async (name: string) => {
    await flushSave();
    setSaveState("idle");
    const shadow = shadowNameOf(name);
    const customized = configs.some((c) => c.kind === "user" && c.name === shadow);
    await loadConfigData(customized ? shadow : name);
  }, [flushSave, configs, loadConfigData]);

  /** 一键恢复默认: 清掉所有影子(你改过的方案都在里面), 回到出厂那套 */
  const resetConfig = useCallback(async () => {
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
  }, [cancelPending, configs, loadConfigList]);

  // 模型目录(ONNX 可选 + 可下载的大模型)。下载完成后要重取一次, "已下载"标记才会变。
  const refreshModels = useCallback(() => {
    api.loadModels()
      .then((m) => { setModelDirs(m.onnx_dirs); setLlmModels(m.llm_models); })
      .catch(() => { setModelDirs([]); setLlmModels([]); });
  }, []);

  const importConfig = useCallback(async (file: File) => {
    try {
      await api.importConfig(file);
      await loadConfigList();
    } catch (e) {
      notifyError(`导入失败: ${(e as Error).message}`);
    }
  }, [loadConfigList, notifyError]);

  /** 跑脱敏时带的配置: 未编辑 → 发口径名(日志显示真实口径); 编辑过 → 发内联对象 */
  const payload = useCallback((): { config?: string | ConfigData } => {
    if (configData && configDirty) return { config: configData };
    if (configRef) return { config: configRef };
    return {};
  }, [configData, configDirty, configRef]);

  const schemeLabel = configs.find((c) => c.name === configRef)?.label ?? configRef;

  useEffect(() => { void loadConfigList(); }, [loadConfigList]);
  useEffect(() => { refreshModels(); }, [refreshModels]);

  return {
    configs, configRef, configData, configKind, configDirty, saveState, saveError,
    modelDirs, llmModels, schemeLabel,
    changeConfig, switchConfig, resetConfig, refreshModels, importConfig, payload,
  };
}
