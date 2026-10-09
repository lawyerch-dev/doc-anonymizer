import { useRef, useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import { EFFECT, ENTITY_TYPES, RECOGNITION_MODES, STRATEGIES, STRATEGY_LABELS, detectorsFor, entityLabel, onnxModelInfo, orderSchemes, recognitionMode } from "../lib/formats";
import { LlmModels } from "./LlmModels";
import type { ConfigData, ConfigRow, LlmModelRow } from "../types";

type Props = {
  configs: ConfigRow[];
  configRef: string | null;
  configData: ConfigData | null;
  configKind: "builtin" | "user" | null;
  modelDirs: string[];
  llmModels: LlmModelRow[];
  onSelectConfig: (name: string) => void;
  onChange: (next: ConfigData) => void;
  onModelsChanged: () => void;
  onSave: () => void;
  onImport: (file: File) => void;
  onExport: () => void;
};

/**
 * 自定义敏感词输入: 自己持一份"自由文本"草稿, 边打边把解析结果提交上去。
 *
 * 为什么不能直接用受控 + 现算: 值要经过 `split/filter(Boolean)`, 分隔符后的空段会被立刻丢掉 ——
 * 打 "甲，" 的瞬间就被规整回 "甲", 用户永远打不出第二个词。所以草稿留在本地, 解析结果照常实时上报
 * (这样"改过没有"是准的), 弹窗关掉也不会丢刚打的字。
 * 换口径时由外层用 `key` 重挂载来重新灌入草稿。
 */
function DictField({ value, onCommit }: { value: string[]; onCommit: (next: string[]) => void }) {
  const [text, setText] = useState(() => value.join("，"));
  return (
    <Input
      id="dictInput"
      className="mt-1 h-8"
      autoComplete="off"
      placeholder="例如：内部项目代号，某客户名"
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        onCommit(e.target.value.split(/[，,]/).map((s) => s.trim()).filter(Boolean));
      }}
    />
  );
}

export function ConfigPanel(props: Props) {
  const { configs, configRef, configData, configKind, modelDirs, llmModels, onSelectConfig, onChange, onModelsChanged } = props;
  const importRef = useRef<HTMLInputElement>(null);
  const d = configData;
  const def = d?.strategies?.DEFAULT ?? "placeholder";
  // 已勾选的 ONNX 模型目录: L3 默认只报"已启用哪几个", 换模型才展开
  const selectedDirs = d?.onnx?.model_dirs ?? [];
  // 「用不用模型来认」: 底下的 detectors 有四项, 但对用户只有这一道选择题
  const mode = d ? recognitionMode(d.detectors) : "none";
  // "两个都用"是合法配置(手写 yaml 会有), 但没在用的时候不必摆出来占位
  const recognitionModes = RECOGNITION_MODES.filter((m) => m.id !== "both" || mode === "both");
  // 选中的那一套: 选项里只放短名, "什么时候用它"放在下面单独一行
  const currentRow = configs.find((c) => c.name === configRef) ?? null;
  const schemeOptions = orderSchemes(configs);

  const setStrategy = (entity: string, value: string) => {
    if (!d) return;
    onChange({ ...d, strategies: { ...d.strategies, [entity]: value } });
  };

  return (
    <div className="space-y-1">
      {/* ---- L1 方案: 选项只放短名, 长解释放下面, 免得下拉里全是字 ---- */}
      <Label className="mb-1.5 block text-xs text-muted-foreground" htmlFor="schemeSel">
        脱敏方案
      </Label>
      <select
        id="schemeSel"
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-[13px]"
        value={configRef ?? ""}
        onChange={(e) => onSelectConfig(e.target.value)}
        title={configRef ?? undefined}
      >
        {schemeOptions.map((c) => (
          <option key={c.name} value={c.name}>
            {c.label}
            {c.kind === "user" ? "（我的）" : ""}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs leading-snug text-muted-foreground">
        {currentRow?.hint || (configKind === "user" ? "你自己保存的方案" : "")}
        {configKind === "user" ? <span className="ml-1 opacity-70">· 我的配置</span> : null}
      </p>
      <p className="text-[11px] leading-snug text-muted-foreground/80">
        不确定选哪个：默认「法律文书交付」（只抹号码与联系方式，人名、机构、金额都留住）；
        要把人名机构也换掉（讲课、写案例）选「通用（本机小模型）」或「最准（本地大模型）」。
      </p>

      <Accordion multiple className="mt-2">
        {/* ---- L2 自定义脱敏 ---- */}
        <AccordionItem value="l2">
          <AccordionTrigger className="text-[13px]">自定义脱敏</AccordionTrigger>
          <AccordionContent>
            {d ? (
              <>
                <label className="mb-2 flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={("PERSON" in d.strategies ? d.strategies.PERSON : def) === "pseudonym"
                      && ("ORG" in d.strategies ? d.strategies.ORG : def) === "pseudonym"}
                    onChange={(e) => {
                      const v = e.target.checked ? "pseudonym" : "redact";
                      onChange({ ...d, strategies: { ...d.strategies, PERSON: v, ORG: v } });
                    }}
                  />
                  用假名替代人名/机构
                </label>

                <table className="w-full border-collapse text-xs">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="border-b px-1.5 py-1 font-medium">类型</th>
                      <th className="border-b px-1.5 py-1 font-medium">策略</th>
                      <th className="border-b px-1.5 py-1 font-medium">效果</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ENTITY_TYPES.map((t) => {
                      const cur = t in d.strategies ? d.strategies[t] : def;
                      return (
                        <tr key={t}>
                          <td className="border-b px-1.5 py-1" title={t}>{entityLabel(t)}</td>
                          <td className="border-b px-1.5 py-1">
                            <select
                              className="rounded border border-input bg-background px-1 py-0.5"
                              value={cur}
                              onChange={(e) => setStrategy(t, e.target.value)}
                              aria-label={`${entityLabel(t)} 的脱敏方式`}
                            >
                              {STRATEGIES.map((s) => (
                                <option key={s} value={s}>{STRATEGY_LABELS[s] ?? s}</option>
                              ))}
                            </select>
                          </td>
                          <td className="border-b px-1.5 py-1 text-muted-foreground">{EFFECT[cur]}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="dictInput">
                  自定义敏感词（逗号分隔）
                </Label>
                <DictField
                  key={configRef ?? ""}
                  value={d.dictionary ?? []}
                  onCommit={(dictionary) => onChange({ ...d, dictionary })}
                />
              </>
            ) : null}
          </AccordionContent>
        </AccordionItem>

        {/* ---- L3 检测引擎 ---- */}
        <AccordionItem value="l3">
          <AccordionTrigger className="text-[13px]">检测引擎</AccordionTrigger>
          <AccordionContent>
            {d ? (
              <>
                <p className="mb-2 text-xs text-muted-foreground">
                  这里只说"靠什么认"；"脱什么"在上面「自定义脱敏」里（每类信息用哪种策略）。
                </p>
                <div className="mb-3">
                  <div className="mb-1 text-xs text-muted-foreground">
                    要不要用模型来认人名、机构、地址
                  </div>
                  <div className="space-y-1">
                    {recognitionModes.map((m) => {
                      const on = mode === m.id;
                      return (
                        <label
                          key={m.id}
                          className="flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-accent/50"
                        >
                          <input
                            type="radio"
                            name="recognition-mode"
                            className="mt-0.5"
                            checked={on}
                            onChange={() => onChange({ ...d, detectors: detectorsFor(m.id) })}
                          />
                          <span className="min-w-0">
                            <span className={on ? "font-medium" : "text-muted-foreground"}>{m.name}</span>
                            <span className="block text-[11px] leading-snug text-muted-foreground">{m.hint}</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* 用过小模型才有模型可挑; 否则这行只是噪音。
                    默认只报"已启用哪几个模型", 要换才展开 —— 目录名(gyr66/pii-engineer)不是用户该做的决定。 */}
                {d.detectors.onnx_ner ? (
                  <div className="mb-3">
                    {modelDirs.length ? (
                      <>
                        {selectedDirs.length ? (
                          <p className="text-[11px] leading-snug text-muted-foreground">
                            已启用：{selectedDirs.map((dir) => onnxModelInfo(dir).name).join(" + ")}
                            {selectedDirs.length > 1 ? "（取并集，重复的会自动去掉）" : ""}
                          </p>
                        ) : (
                          <p className="text-[11px] text-destructive">
                            至少要选一个模型 —— 一个都不选，这一层就起不来。
                          </p>
                        )}
                        <details className="mt-1">
                          <summary className="cursor-pointer text-xs text-muted-foreground">调整模型</summary>
                          <p className="mt-1.5 text-[11px] text-muted-foreground">
                            推荐两个都选：实测覆盖率最高；它们认的类别有重叠，重复的会自动去掉。
                          </p>
                          <div className="mt-1 space-y-1">
                            {modelDirs.map((dir) => {
                              const info = onnxModelInfo(dir);
                              const on = selectedDirs.includes(dir);
                              return (
                                <label
                                  key={dir}
                                  className="flex cursor-pointer items-start gap-2 rounded-md border border-input px-2 py-1.5 text-xs hover:bg-accent/50"
                                  title={dir}
                                >
                                  <input
                                    type="checkbox"
                                    className="mt-0.5"
                                    checked={on}
                                    onChange={(e) => {
                                      const next = e.target.checked
                                        ? [...selectedDirs, dir]
                                        : selectedDirs.filter((v) => v !== dir);
                                      onChange({ ...d, onnx: { ...d.onnx, model_dirs: next } });
                                    }}
                                  />
                                  <span className="min-w-0">
                                    <span className={on ? "font-medium" : "text-muted-foreground"}>
                                      {info.name}
                                      {info.recommended ? (
                                        <span className="ml-1.5 rounded bg-selected/10 px-1 text-[10px] text-selected">
                                          推荐
                                        </span>
                                      ) : null}
                                    </span>
                                    <span className="block text-[11px] leading-snug text-muted-foreground">
                                      {info.hint}
                                    </span>
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </details>
                      </>
                    ) : (
                      <p className="text-[11px] text-muted-foreground">
                        本机还没有可用模型 —— 先跑 <code className="rounded bg-muted px-1">npm run models</code> 下载
                      </p>
                    )}
                  </div>
                ) : null}

                {/* 勾了「本地大模型」就是"选一个模型"：起服务是 app 的事，
                    不摆地址/别名/启动命令 —— 那些是实现细节，不是用户要做的决定。 */}
                {d.detectors.llm_ner ? (
                  llmModels.length ? (
                    <>
                      <LlmModels
                        models={llmModels}
                        modelId={d.llm?.model_id ?? ""}
                        onChangeModelId={(v) => onChange({ ...d, llm: { ...d.llm, model_id: v } })}
                        onModelsChanged={onModelsChanged}
                      />
                      <p className="mb-2 text-[11px] leading-snug text-muted-foreground">
                        开跑前会自动把本机服务起好（换了模型就换掉它）；起不来会直接报错，不会静默跳过这一层。
                      </p>
                    </>
                  ) : (
                    <p className="mb-2 text-[11px] text-muted-foreground">
                      本机还没有可用模型 —— 先跑 <code className="rounded bg-muted px-1">npm run models</code> 下载
                    </p>
                  )
                ) : null}

                <p className="text-[11px] leading-snug text-muted-foreground">
                  固定写法的号码、邮箱，以及你填的词表，一直都在认（这些不靠模型，也没有关掉的理由）——
                  不想动某一类，去上面把它的策略设成「保持原样」。
                </p>
              </>
            ) : null}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="mt-2 flex gap-1.5">
        <Button variant="outline" size="sm" className="flex-1" onClick={props.onSave}>保存为…</Button>
        <input
          ref={importRef}
          type="file"
          accept=".yaml,.yml"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) props.onImport(f);
            e.target.value = "";
          }}
        />
        <Button variant="outline" size="sm" className="flex-1" onClick={() => importRef.current?.click()}>
          导入
        </Button>
        <Button variant="outline" size="sm" className="flex-1" onClick={props.onExport} disabled={!configRef}>
          导出
        </Button>
      </div>
    </div>
  );
}
