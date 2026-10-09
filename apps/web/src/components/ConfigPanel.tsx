import { useRef, useState } from "react";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import { DETECTORS, DETECTOR_LABELS, EFFECT, ENTITY_TYPES, STRATEGIES, STRATEGY_LABELS, entityLabel } from "../lib/formats";
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
                  勾选要用的识别方式，都用同一份文档试一遍；同一处被多个认出来时只算一次
                  （规则与敏感词优先于大模型）。
                </p>
                <div className="mb-3 space-y-1">
                  {DETECTORS.map((n) => {
                    const { name, hint } = DETECTOR_LABELS[n];
                    const on = Boolean(d.detectors[n]);
                    return (
                      <label
                        key={n}
                        className="flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-accent/50"
                      >
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={on}
                          onChange={(e) => onChange({ ...d, detectors: { ...d.detectors, [n]: e.target.checked } })}
                        />
                        <span className="min-w-0">
                          <span className={on ? "font-medium" : "text-muted-foreground"}>{name}</span>
                          <span className="block text-[11px] leading-snug text-muted-foreground">{hint}</span>
                        </span>
                      </label>
                    );
                  })}
                </div>

                {/* 只有勾了「中文人名与机构」才有模型目录可挑; 否则这行只是噪音 */}
                {d.detectors.onnx_ner ? (
                  <div className="mb-3">
                    <div className="mb-1 text-xs text-muted-foreground">用哪个中文模型（可多选）</div>
                    {modelDirs.length ? (
                      <div className="space-y-1">
                        {modelDirs.map((dir) => (
                          <label
                            key={dir}
                            className="flex cursor-pointer items-center gap-2 rounded-md border border-input px-2 py-1 text-xs hover:bg-accent/50"
                            title={dir}
                          >
                            <input
                              type="checkbox"
                              checked={(d.onnx?.model_dirs ?? []).includes(dir)}
                              onChange={(e) => {
                                const cur = d.onnx?.model_dirs ?? [];
                                const next = e.target.checked
                                  ? [...cur, dir]
                                  : cur.filter((v) => v !== dir);
                                onChange({ ...d, onnx: { ...d.onnx, model_dirs: next } });
                              }}
                            />
                            <span className="truncate font-mono text-[11px]">{dir}</span>
                          </label>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] text-muted-foreground">
                        本机还没有可用模型 —— 先跑 <code className="rounded bg-muted px-1">npm run models</code> 下载
                      </p>
                    )}
                  </div>
                ) : null}

                {/* 同理: 没勾「本地大模型」就别问地址, 免得像"已经在用" */}
                {d.detectors.llm_ner ? (
                  <>
                    <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmUrl">
                      模型服务地址
                    </Label>
                    <Input
                      id="llmUrl" className="mt-1 h-8"
                      inputMode="url" autoComplete="off" spellCheck={false}
                      placeholder="http://127.0.0.1:8080/v1"
                      value={d.llm?.base_url ?? ""}
                      onChange={(e) => onChange({ ...d, llm: { ...d.llm, base_url: e.target.value } })}
                    />
                    <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmModel">
                      模型名
                    </Label>
                    <Input
                      id="llmModel" className="mt-1 h-8"
                      autoComplete="off" spellCheck={false}
                      value={d.llm?.model ?? ""}
                      onChange={(e) => onChange({ ...d, llm: { ...d.llm, model: e.target.value } })}
                    />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      服务没起来时，脱敏会在开始前报错并告诉你原因，不会静默跳过这一层。
                    </p>
                  </>
                ) : null}
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
