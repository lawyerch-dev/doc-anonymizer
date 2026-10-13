import { useRef, useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { EFFECT, ENTITY_TYPES, RECOGNITION_MODES, REVERSIBLE, STRATEGIES, STRATEGY_LABELS, detectorsFor, entityLabel, onnxModelInfo, orderSchemes, recognitionMode, shadowNameOf, shadowState, visibleSchemes } from "../lib/formats";
import { LlmModels } from "./LlmModels";
import { Select } from "./Select";
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
  // 「影子」= 你在某套内置上改动后落的那份用户配置: 不进下拉(还是那三套), 只标「已改」
  const { shadows, isShadow } = shadowState(configs);
  // 当前口径是影子时, 下拉要选中的是它那套内置(不然出现"列表里没有这个值"的空白态)
  const shownRef = configRef && isShadow(configRef) ? `${configRef}.yaml` : configRef;
  // 选中的那一套: 选项里只放短名, "什么时候用它"放在下面单独一行
  const currentRow = configs.find((c) => c.name === shownRef) ?? null;
  const schemeOptions = orderSchemes(visibleSchemes(configs)).filter((c) => !isShadow(c.name));

  const setStrategy = (entity: string, value: string) => {
    if (!d) return;
    onChange({ ...d, strategies: { ...d.strategies, [entity]: value } });
  };

  return (
    <div className="space-y-3">
      {/* 方案是一个折叠项: L1 选哪套 + L2 脱什么 + L3 靠什么认 —— 三层是同一件事的三层,
          归在一个「脱敏方案」下面; 触发器的右侧直接显示当前选的是哪套。 */}
      <Accordion multiple>
        <AccordionItem value="scheme">
          <AccordionTrigger
            className="py-3.5 text-base font-semibold hover:no-underline"
            title="选一套方案，再按需细调「脱什么」与「靠什么认」。"
          >
            {/* 居中而非基线对齐: 16px 标题与 12px 当前方案名同排, 基线对齐会把小字压低 1px */}
            <span className="flex min-w-0 flex-1 items-center gap-2 pr-1">
              脱敏方案
              <span className="ml-auto shrink-0 text-xs font-normal text-muted-foreground">
                {currentRow?.label ?? ""}
              </span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-5 pb-5">
            {/* ---- 方案: 这一项里的主控件, 给足体量; 长解释进 title ---- */}
            <div className="space-y-2.5">
            <Select
              id="schemeSel"
              aria-label="脱敏方案"
              wrapperClassName="w-full"
              className="h-10 font-medium"
              value={shownRef ?? ""}
              onChange={(e) => onSelectConfig(e.target.value)}
              title={"不确定选哪个：默认「通用」够用（号码、人名、机构、地址都能认）；\n只要号码、跑得最快选「最快」；要说认得更全（讲课、写案例）选「最准」。"}
            >
              {schemeOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.label}
                  {shadows.has(shadowNameOf(c.name)) ? "（已改）" : ""}
                  {c.kind === "user" ? "（我的）" : ""}
                </option>
              ))}
            </Select>
            <Note title={currentRow?.hint}>
              {currentRow?.hint || (configKind === "user" ? "你自己保存的方案" : "")}
            </Note>
            </div>

      {/* ---- 识别方式: 方案自带一套引擎/模型, 这里是覆盖它的地方。
           排在「脱敏规则」前面: 先定靠什么认, 再定认出来怎么脱 ---- */}
      <div>
        <h4 className="mb-2.5 text-sm font-semibold text-foreground"
            title="号码、邮箱与你填的词表一直都在认，不用配；人名、机构、地址这类才需要模型。">
          识别方式（用不用模型）
        </h4>
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
                      {/* 模型清单直接铺开(不折起来): 选哪几个模型是这一层的实质内容, 藏一层要多点一下 */}
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
                    </div>
                  ) : (
                    <Note title="选「本机小模型」后，识别能力会随首次准备自动装好。">
                      本机识别能力还没装好 —— 保持选中「本机小模型」，首次准备时会自动装好
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
                    <Note title="选一个模型后会自动装好，稍等片刻即可用。">
                      本机识别能力还没装好 —— 保持选中「本地大模型」，自动装好后就能用
                    </Note>
                  )
                ) : null}
              </div>
            ) : null}
      </div>

      {/* ---- 脱敏规则: 系统默认与你的覆盖都在这一张表里(值就是从上面那套方案来的) ---- */}
      <div>
        <h4 className="mb-2.5 text-sm font-semibold text-foreground"
            title="按信息类型逐个指定怎么处理：盖掉、打码、换成假名/占位符、删除，或保持原样。">
          脱敏规则
        </h4>
            {d ? (
              <div className="space-y-5">
                {/* 自定义敏感词: "我关心的词"这一类(项目代号、客户名…)的补充; 命中后怎么处理由下面那张表定 */}
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
                              <Select
                                className="h-7 text-[13px]"
                                value={cur}
                                onChange={(e) => setStrategy(t, e.target.value)}
                                aria-label={`${entityLabel(t)} 的脱敏方式`}
                              >
                                {STRATEGIES.map((s) => (
                                  <option key={s} value={s}>{STRATEGY_LABELS[s] ?? s}</option>
                                ))}
                              </Select>
                            </td>
                            <td className="border-b px-2 py-1.5 text-muted-foreground">
                              {EFFECT[cur]}
                              {/* 不可逆的策略在这里说清楚 —— 否则用户选了 mask 才想起来"回头怎么填回去" */}
                              {REVERSIBLE[cur] === false ? (
                                <span className="ml-1 text-destructive/80" title="替换值里已经没有原文, 事后无法还原">
                                  不可还原
                                </span>
                              ) : null}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
      </div>

          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="flex gap-2 pt-1">
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