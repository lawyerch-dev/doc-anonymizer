import { useRef, useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import { EFFECT, ENTITY_TYPES, RECOGNITION_MODES, STRATEGIES, STRATEGY_LABELS, detectorsFor, entityLabel, onnxModelInfo, orderSchemes, recognitionMode, visibleSchemes } from "../lib/formats";
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
      className="h-9"
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

/** 分组小标题: 统一字重与颜色, 别让每块各写一套 */
function Field({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <div className="mb-2 text-[13px] font-medium text-foreground" title={title}>
      {children}
    </div>
  );
}

/** 一句说明: 只留一行, 更长的解释进 title(悬停才看) */
function Note({ children, title, className = "" }: { children: React.ReactNode; title?: string; className?: string }) {
  return (
    <p className={`text-xs leading-relaxed text-muted-foreground ${className}`} title={title}>
      {children}
    </p>
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
  const schemeOptions = orderSchemes(visibleSchemes(configs));

  const setStrategy = (entity: string, value: string) => {
    if (!d) return;
    onChange({ ...d, strategies: { ...d.strategies, [entity]: value } });
  };

  return (
    <div className="space-y-7">
      {/* ---- L1 方案: 这是整个面板的主控件, 给足体量; 长解释进 title ---- */}
      <section className="space-y-2.5">
        <Label className="block text-[13px] font-medium" htmlFor="schemeSel">
          脱敏方案
        </Label>
        <select
          id="schemeSel"
          className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          value={configRef ?? ""}
          onChange={(e) => onSelectConfig(e.target.value)}
          title={"不确定选哪个：默认「通用」够用（号码、人名、机构、地址都能认）；\n只要号码、跑得最快选「最快」；要说认得更全（讲课、写案例）选「最准」。"}
        >
          {schemeOptions.map((c) => (
            <option key={c.name} value={c.name}>
              {c.label}
              {c.kind === "user" ? "（我的）" : ""}
            </option>
          ))}
        </select>
        <Note title={currentRow?.hint}>
          {currentRow?.hint || (configKind === "user" ? "你自己保存的方案" : "")}
          {configKind === "user" ? <span className="ml-1 opacity-70">· 我的配置</span> : null}
        </Note>
      </section>

      <Accordion multiple className="-mt-2">
        {/* ---- L2 自定义脱敏 ---- */}
        <AccordionItem value="l2">
          <AccordionTrigger
            className="py-3.5 text-base font-semibold hover:no-underline"
            title="按信息类型逐个指定怎么处理：盖掉、打码、换成假名/占位符、删除，或保持原样。"
          >
            自定义脱敏
          </AccordionTrigger>
          <AccordionContent className="pb-5">
            {d ? (
              <div className="space-y-5">
                <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={("PERSON" in d.strategies ? d.strategies.PERSON : def) === "pseudonym"
                      && ("ORG" in d.strategies ? d.strategies.ORG : def) === "pseudonym"}
                    onChange={(e) => {
                      const v = e.target.checked ? "pseudonym" : "redact";
                      onChange({ ...d, strategies: { ...d.strategies, PERSON: v, ORG: v } });
                    }}
                  />
                  用假名替代人名/机构
                </label>

                <div>
                  <Field title="「保持原样」＝这一类不处理；其余策略见下拉选项与右侧效果示例。">
                    每类信息怎么处理
                  </Field>
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="text-left text-xs text-muted-foreground">
                        <th className="border-b px-2 py-2 font-medium">类型</th>
                        <th className="border-b px-2 py-2 font-medium">策略</th>
                        <th className="border-b px-2 py-2 font-medium">效果</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ENTITY_TYPES.map((t) => {
                        const cur = t in d.strategies ? d.strategies[t] : def;
                        return (
                          <tr key={t}>
                            <td className="border-b px-2 py-1.5" title={t}>{entityLabel(t)}</td>
                            <td className="border-b px-2 py-1.5">
                              <select
                                className="h-7 rounded-md border border-input bg-background px-2 text-[13px]"
                                value={cur}
                                onChange={(e) => setStrategy(t, e.target.value)}
                                aria-label={`${entityLabel(t)} 的脱敏方式`}
                              >
                                {STRATEGIES.map((s) => (
                                  <option key={s} value={s}>{STRATEGY_LABELS[s] ?? s}</option>
                                ))}
                              </select>
                            </td>
                            <td className="border-b px-2 py-1.5 text-muted-foreground">{EFFECT[cur]}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div>
                  <Field title="你自己关心的词（项目代号、客户名…），命中后按「自定义」那类的策略处理。">
                    自定义敏感词（逗号分隔）
                  </Field>
                  <DictField
                    key={configRef ?? ""}
                    value={d.dictionary ?? []}
                    onCommit={(dictionary) => onChange({ ...d, dictionary })}
                  />
                </div>
              </div>
            ) : null}
          </AccordionContent>
        </AccordionItem>

        {/* ---- L3 检测引擎 ---- */}
        <AccordionItem value="l3">
          <AccordionTrigger
            className="py-3.5 text-base font-semibold hover:no-underline"
            title="这一层只管「靠什么认」；「脱什么」在上面「自定义脱敏」里。号码、邮箱与你填的词表一直都在认，不用配。"
          >
            检测引擎
          </AccordionTrigger>
          <AccordionContent className="pb-5">
            {d ? (
              <div className="space-y-5">
                <div>
                  <Field title="不用模型＝只认固定写法的号码与你的词表。选模型才会认人名、机构、地址。">
                    要不要用模型来认人名、机构、地址
                  </Field>
                  <div className="space-y-1.5">
                    {recognitionModes.map((m) => {
                      const on = mode === m.id;
                      return (
                        <label
                          key={m.id}
                          className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                            on ? "border-selected bg-selected/10 ring-1 ring-selected/40" : "border-input hover:bg-accent/50"
                          }`}
                        >
                          <input
                            type="radio"
                            name="recognition-mode"
                            className="mt-0.5 size-4"
                            checked={on}
                            onChange={() => onChange({ ...d, detectors: detectorsFor(m.id) })}
                          />
                          <span className="min-w-0">
                            <span className={on ? "font-medium" : ""}>{m.name}</span>
                            <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{m.hint}</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* 用过小模型才有模型可挑; 否则这行只是噪音。
                    默认只报"已启用哪几个模型", 要换才展开 —— 目录名(gyr66/pii-engineer)不是用户该做的决定。 */}
                {d.detectors.onnx_ner ? (
                  modelDirs.length ? (
                    <div>
                      <Field title="推荐两个都选：实测覆盖率最高；它们认的类别有重叠，重复的会自动去掉。">
                        本机小模型
                      </Field>
                      {selectedDirs.length ? (
                        <Note>
                          已启用：{selectedDirs.map((dir) => onnxModelInfo(dir).name).join(" + ")}
                          {selectedDirs.length > 1 ? "（取并集，重复的会自动去掉）" : ""}
                        </Note>
                      ) : (
                        <p className="text-xs text-destructive">至少要选一个模型 —— 一个都不选，这一层就起不来。</p>
                      )}
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                          调整模型
                        </summary>
                        <div className="mt-2 space-y-1.5">
                          {modelDirs.map((dir) => {
                            const info = onnxModelInfo(dir);
                            const on = selectedDirs.includes(dir);
                            return (
                              <label
                                key={dir}
                                className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors ${
                                  on ? "border-selected/60 bg-selected/5" : "border-input hover:bg-accent/50"
                                }`}
                                title={dir}
                              >
                                <input
                                  type="checkbox"
                                  className="mt-0.5 size-4"
                                  checked={on}
                                  onChange={(e) => {
                                    const next = e.target.checked
                                      ? [...selectedDirs, dir]
                                      : selectedDirs.filter((v) => v !== dir);
                                    onChange({ ...d, onnx: { ...d.onnx, model_dirs: next } });
                                  }}
                                />
                                <span className="min-w-0">
                                  <span className={on ? "font-medium" : ""}>
                                    {info.name}
                                    {info.recommended ? (
                                      <span className="ml-1.5 rounded bg-selected/10 px-1.5 py-px text-[10px] text-selected">
                                        推荐
                                      </span>
                                    ) : null}
                                  </span>
                                  <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                                    {info.hint}
                                  </span>
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </details>
                    </div>
                  ) : (
                    <Note title="命令行执行 npm run models 即可下载；下载后回到这里就能选。">
                      本机还没有可用模型 —— 先跑 <code className="rounded bg-muted px-1.5 py-0.5">npm run models</code> 下载
                    </Note>
                  )
                ) : null}

                {/* 勾了「本地大模型」就是"选一个模型"：起服务是 app 的事，
                    不摆地址/别名/启动命令 —— 那些是实现细节，不是用户要做的决定。 */}
                {d.detectors.llm_ner ? (
                  llmModels.length ? (
                    <div title="开跑前会自动把本机服务起好（换了模型就换掉它）；起不来会直接报错，不会静默跳过这一层。">
                      <LlmModels
                        models={llmModels}
                        modelId={d.llm?.model_id ?? ""}
                        onChangeModelId={(v) => onChange({ ...d, llm: { ...d.llm, model_id: v } })}
                        onModelsChanged={onModelsChanged}
                      />
                    </div>
                  ) : (
                    <Note title="命令行执行 npm run models 即可下载；下载后回到这里就能选。">
                      本机还没有可用模型 —— 先跑 <code className="rounded bg-muted px-1.5 py-0.5">npm run models</code> 下载
                    </Note>
                  )
                ) : null}
              </div>
            ) : null}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="flex gap-2 pt-1">
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