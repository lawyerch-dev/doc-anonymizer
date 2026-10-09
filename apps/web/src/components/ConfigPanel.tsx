import { useRef, useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import { EFFECT, ENTITY_TYPES, STRATEGIES, entityLabel } from "../lib/formats";
import type { ConfigData, ConfigRow } from "../types";

type Props = {
  configs: ConfigRow[];
  configRef: string | null;
  configData: ConfigData | null;
  configKind: "builtin" | "user" | null;
  modelDirs: string[];
  onSelectConfig: (name: string) => void;
  onChange: (next: ConfigData) => void;
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
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        onCommit(e.target.value.split(/[，,]/).map((s) => s.trim()).filter(Boolean));
      }}
    />
  );
}

export function ConfigPanel(props: Props) {
  const { configs, configRef, configData, configKind, modelDirs, onSelectConfig, onChange } = props;
  const importRef = useRef<HTMLInputElement>(null);
  const d = configData;
  const def = d?.strategies?.DEFAULT ?? "placeholder";

  const setStrategy = (entity: string, value: string) => {
    if (!d) return;
    onChange({ ...d, strategies: { ...d.strategies, [entity]: value } });
  };

  return (
    <div className="space-y-1">
      {/* ---- L1 口径 ---- */}
      <Label className="mb-1.5 block text-xs text-muted-foreground">脱敏口径</Label>
      <select
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-[13px]"
        value={configRef ?? ""}
        onChange={(e) => onSelectConfig(e.target.value)}
      >
        {configs.map((c) => (
          <option key={c.name} value={c.name}>
            {c.label}
            {c.kind === "user" ? "（我的）" : ""}
            {c.current ? "（当前）" : ""}
          </option>
        ))}
      </select>
      <div className="mt-1 text-xs text-muted-foreground">
        {configRef ? `${configRef}${configKind === "user" ? " · 我的配置" : " · 内置"}` : ""}
      </div>

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
                            >
                              {STRATEGIES.map((s) => (
                                <option key={s} value={s}>{s}</option>
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
                <div className="mb-2">
                  {(["rule", "dictionary", "onnx_ner", "llm_ner"] as const).map((n) => (
                    <label key={n} className="block text-xs">
                      <input
                        type="checkbox"
                        checked={Boolean(d.detectors[n])}
                        onChange={(e) => onChange({ ...d, detectors: { ...d.detectors, [n]: e.target.checked } })}
                      />{" "}
                      {n}
                    </label>
                  ))}
                </div>

                <Label className="block text-xs text-muted-foreground" htmlFor="modelDirs">
                  ONNX 模型目录（可多选）
                </Label>
                <select
                  id="modelDirs"
                  multiple
                  size={3}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-xs"
                  value={d.onnx?.model_dirs ?? []}
                  onChange={(e) => onChange({
                    ...d,
                    onnx: { ...d.onnx, model_dirs: Array.from(e.target.selectedOptions).map((o) => o.value) },
                  })}
                >
                  {modelDirs.map((dir) => (
                    <option key={dir} value={dir}>{dir}</option>
                  ))}
                </select>

                <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmUrl">LLM 地址</Label>
                <Input
                  id="llmUrl" className="mt-1 h-8" value={d.llm?.base_url ?? ""}
                  onChange={(e) => onChange({ ...d, llm: { ...d.llm, base_url: e.target.value } })}
                />
                <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmModel">LLM 模型名</Label>
                <Input
                  id="llmModel" className="mt-1 h-8" value={d.llm?.model ?? ""}
                  onChange={(e) => onChange({ ...d, llm: { ...d.llm, model: e.target.value } })}
                />
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
