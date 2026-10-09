# 产品界面迁移到 Vite + React 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把产品界面 `apps/web/` 从零构建手写件（`index.html` + `app.css` + `app.js`）迁到 Vite 5 + React 19 + TypeScript + Tailwind 4，复用共享组件库 `@doc-anonymizer/ui`，并顺带优化布局与加暗色。

**Architecture:** `docanon web` 运行期仍只发静态文件（**零 node、全离线**），只是发的内容从零构建三件套换成 Vite 构建出的 `apps/web/dist`。`resources.LAYOUT["web"]` 一处改指 `dist`；服务端只改静态映射，API 一字不改。构建期用 npm workspaces（根 `npm install` 一次）。

**Tech Stack:** Vite 5 · React 19 · TypeScript 5 · Tailwind CSS 4（`@tailwindcss/vite`）· `@doc-anonymizer/ui`（velora 100 组件 + shadcn 基础件 + 设计 token）

**Spec:** [docs/specs/2026-10-09-web-ui-vite-migration-design.md](../../specs/2026-10-09-web-ui-vite-migration-design.md)

---

## 不可违反的三条硬约束

1. **运行期零 node、全离线**——`docanon web` 不发 node，只发静态文件。
2. **组件只在 `packages/ui`**——app 里不许出现 velora 组件源码，只许 `import`（`tests/test_docs.py` 会拦）。
3. **DOM 契约**——E2E（`tests/e2e/webkit/*.mjs`）依赖 `.preset` `#run` `#paneSrc` `#paneOut` `#stats`，迁移中这几个钩子的语义与位置**不变**。

## 已实测的坑（写计划时验证过，别踩）

- **`packages/ui` 的 `blocks/` 有 3 个既存 tsc 报错**（实测：`npx tsc --noEmit -p packages/ui/tsconfig.json`）：
  `blocks/faq-accordion.tsx`、`blocks/faq-two-column.tsx`、`blocks/navbar-mega.tsx`。
  因为 `apps/web` 的 `tsc --noEmit` 会**一起检查被 import 的 kit 源码**，
  所以 **`apps/web` 只许 import `primitives/*`**（button/input/label/badge/accordion 这批是干净的）；
  一旦 import `blocks/*`，类型检查就会因为 kit 的报错而红。要修 kit 的报错请另开一次改动，别混进本次迁移。
- `.gitignore` 第 11 行的通用 `dist/` 已经覆盖 `apps/web/dist/`，**不需要**新增忽略规则。
- `apps/web/index.html` 同时是 Vite 的入口模板（源）与产物名——所以产物必须落 `dist/`；
  把 `outDir` 设成项目根会自我覆盖，且 `emptyOutDir` 有清空源码的风险。

## 文件结构

**新增（`apps/web/` 从"三个静态件"变成 Vite 项目）**

| 文件 | 职责 |
|---|---|
| `apps/web/package.json` | `@doc-anonymizer/web`：`dev`(vite) / `build`(tsc --noEmit + vite build) / `preview` |
| `apps/web/vite.config.ts` | React + Tailwind 插件、产物落 `dist`、dev 期 proxy 五条前缀到后端 |
| `apps/web/tsconfig.json` | 严格 TS，`noEmit` |
| `apps/web/index.html` | Vite 入口模板（源）；挂 `#root`，先加载 file-viewer 全局脚本 |
| `apps/web/src/main.tsx` | React 挂载 |
| `apps/web/src/App.tsx` | 布局骨架 + 顶层状态（唯一持有 state 的地方） |
| `apps/web/src/types.ts` | 与后端契约一一对应的类型 |
| `apps/web/src/lib/api.ts` | 所有 fetch 封装成 typed client |
| `apps/web/src/lib/formats.ts` | 实体类型 / 策略 / 效果示例 / 位置文案 |
| `apps/web/src/lib/viewer.ts` | file-viewer 全局脚本的命令式封装 |
| `apps/web/src/components/PresetList.tsx` | 文档选择（`.preset`） |
| `apps/web/src/components/ConfigPanel.tsx` | L1/L2/L3 口径面板 |
| `apps/web/src/components/Preview.tsx` | 原文/脱敏后预览挂载点 |
| `apps/web/src/components/StatsCard.tsx` | 命中统计（`#stats`） |
| `apps/web/src/components/LogModal.tsx` | 运行日志弹窗 |
| `apps/web/src/styles.css` | `@import theme.css` + `@source` 到 ui 包 |

**删除**：`apps/web/app.css`、`apps/web/app.js`（逻辑全部迁进 `src/`）。

**修改**

| 文件 | 改什么 |
|---|---|
| `package.json`（根） | `workspaces` 加 `apps/web`；新增 `build:web` / `dev:backend`；`test:py` / `test:strict` 前置构建 |
| `packages/docanon-core/src/docanon_core/resources.py` | `LAYOUT["web"]`: `apps/web` → `apps/web/dist` |
| `packages/docanon-core/src/docanon_core/server/routes.py` | 删 `_WEB_ASSETS`，改为发 `dist/index.html` + `dist/assets/*` |
| `packages/docanon-core/tests/test_resources.py` | 断言改成 `apps/web/dist/index.html` |
| `packages/docanon-core/tests/test_server.py` | 新增：`/` 发构建后的 index、`/assets/*` 可访问 |
| `tests/test_docs.py` | `RUNTIME_PREFIXES` 加 `apps/web/dist`（构建产物不是"真路径"） |
| `tests/test_check_scope.py` | 新增：`apps/web/` 改动选前端检查 |
| `scripts/check_scope.py` | 前端组加 `apps/web/`；从 `MANUAL` 移除 `apps/web/`（不再是"零构建、无自动化"） |
| `scripts/dev.sh` | 新增 `webui` 子命令（并发达起后端 + Vite dev + proxy）；`doctor` 增加 dist 检查 |
| `.gitignore` | 无需改：第 11 行通用 `dist/` 已覆盖 `apps/web/dist/` |
| 文档 | README(.en) / CONTRIBUTING(.en) / docs/architecture(.en) / AGENTS.md / rules 03·07 / packages/ui/README / website/README / CHANGELOG / 决策笔记 |

---

## Task 1: Vite 项目脚手架，产物落 dist

**Files:**
- Create: `apps/web/package.json`, `apps/web/vite.config.ts`, `apps/web/tsconfig.json`, `apps/web/src/main.tsx`, `apps/web/src/App.tsx`, `apps/web/src/styles.css`
- Modify: `apps/web/index.html`
- Modify: `package.json`（根，仅 `workspaces`）

- [ ] **Step 1: 写 `apps/web/package.json`**

```json
{
  "name": "@doc-anonymizer/web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "description": "产品界面: Vite + React + Tailwind 4, 复用 @doc-anonymizer/ui; 产物 dist/ 由 docanon web 静态发出",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@doc-anonymizer/ui": "*",
    "react": "^19.3.0",
    "react-dom": "^19.3.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^4",
    "typescript": "^5",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: 写 `apps/web/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// dev 期把后端的五条前缀转发过去(docanon web 默认 8000); 生产不走这里(dist 由 docanon web 直发)
const BACKEND = process.env.DOCANON_BACKEND || "http://127.0.0.1:8000";
const PROXIED = ["/api", "/samples", "/uploads", "/outputs", "/file-viewer", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 产物落 apps/web/dist: 与源码不同层, emptyOutDir 可安全清空(不会覆盖源码)
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: Object.fromEntries(PROXIED.map((p) => [p, { target: BACKEND }])),
  },
});
```

- [ ] **Step 3: 写 `apps/web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "verbatimModuleSyntax": true,
    "types": ["vite/client"]
  },
  "include": ["src", "vite.config.ts"]
}
```

- [ ] **Step 4: 改写 `apps/web/index.html`（Vite 入口模板）**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>文档脱敏工具</title>
</head>
<body>
<div id="root"></div>
<!-- file-viewer 是全局 IIFE(docanon web 从 /file-viewer/ 发); 必须先于 app 模块执行。
     type="module" 的脚本天然 defer, 会排在这个经典脚本之后。 -->
<script src="/file-viewer/flyfish-file-viewer-web-full.iife.js"></script>
<script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: 写 `apps/web/src/styles.css`**

```css
@import "tailwindcss";
@import "@doc-anonymizer/ui/theme.css";

/* Tailwind 4 要扫到共享组件包与本地源码, 否则 kit 里的类名会被摇掉 */
@source "../../../packages/ui/src";
@source "../";
```

- [ ] **Step 6: 写最小 `apps/web/src/main.tsx` 与 `apps/web/src/App.tsx`**

`apps/web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

const el = document.getElementById("root");
if (!el) throw new Error("缺 #root 挂载点");
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`apps/web/src/App.tsx`（本步只要"能编译、能构建"，功能留给后面任务）:

```tsx
import { Button } from "@doc-anonymizer/ui/primitives/button";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <h1 className="text-lg font-semibold">文档脱敏工具</h1>
      <Button id="run" disabled>开始脱敏</Button>
    </div>
  );
}
```

- [ ] **Step 7: 根 `package.json` 的 `workspaces` 加 `apps/web`**

```json
  "workspaces": [
    "packages/ui",
    "website",
    "apps/web"
  ],
```

- [ ] **Step 8: 装依赖并确认构建产出 dist**

Run: `npm install --no-audit --no-fund && npm run build -w @doc-anonymizer/web`
Expected: 命令成功；`apps/web/dist/index.html` 与 `apps/web/dist/assets/*.js`、`*.css` 存在。

用 `ls apps/web/dist` 确认。若 `npm install` 报版本无法解析（`vite` / `@vitejs/plugin-react` 的 peer 冲突），按 npm 的建议调整 `apps/web/package.json` 里的版本区间后重跑，不要跳过这一步。

- [ ] **Step 9: 提交**

```bash
git add apps/web/package.json apps/web/vite.config.ts apps/web/tsconfig.json \
        apps/web/index.html apps/web/src/main.tsx apps/web/src/App.tsx \
        apps/web/src/styles.css package.json package-lock.json
git commit -m "build(web): apps/web 改建 Vite + React + Tailwind, 产物落 dist"
```

---

## Task 2: 后端改为托管 dist（LAYOUT + routes + 测试）

**Files:**
- Modify: `packages/docanon-core/src/docanon_core/resources.py:27`
- Modify: `packages/docanon-core/src/docanon_core/server/routes.py:42-64,117-144`
- Modify: `packages/docanon-core/tests/test_resources.py:45`
- Modify: `packages/docanon-core/tests/test_server.py`（末尾追加两条）
- Modify: `tests/test_docs.py`（`RUNTIME_PREFIXES`）

- [ ] **Step 1: 写失败的测试——资源根指向 dist**

在 `packages/docanon-core/tests/test_resources.py` 把第 45 行改成：

```python
    assert resources.web_index() == fake.resolve() / "apps" / "web" / "dist" / "index.html"
```

- [ ] **Step 2: 跑测试确认它失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_resources.py -q`
Expected: FAIL（`web_index()` 仍返回 `apps/web/index.html`）

- [ ] **Step 3: 改 `resources.py` 的 LAYOUT**

把

```python
    "web": "apps/web",                        # 前端静态件(index.html / app.css / app.js)
```

改成

```python
    "web": "apps/web/dist",                   # 前端构建产物(Vite 输出; 源码在 apps/web/src)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_resources.py packages/docanon-core/tests/test_layout.py -q`
Expected: PASS（`test_layout.py` 的 `web_index().is_file()` 也通过——因为 Task 1 已构建出 dist）

- [ ] **Step 5: 写失败的测试——服务端从 dist 发页面与资源**

在 `packages/docanon-core/tests/test_server.py` 末尾追加：

```python
def test_root_serves_the_built_index(ephemeral_server):
    """`docanon web` 发的必须是构建产物(dist/index.html), 不是源码入口。"""
    with urllib.request.urlopen(ephemeral_server + "/", timeout=5) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        html = resp.read().decode("utf-8")
    assert '<div id="root">' in html, "发出去的不是 Vite 构建后的 index"
    assert "/src/main.tsx" not in html, "发出去的是源码入口(未构建)"


def test_built_assets_are_served(ephemeral_server):
    """带哈希的 JS/CSS 落在 /assets/ 下, 必须能取到 —— 取不到就是白屏。"""
    from docanon_core import resources

    assets = sorted((resources.path("web") / "assets").glob("*.js"))
    assert assets, "构建产物里没有 assets/*.js, 先跑 npm run build:web"
    with urllib.request.urlopen(
        f"{ephemeral_server}/assets/{assets[0].name}", timeout=5
    ) as resp:
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type", "")
```

- [ ] **Step 6: 跑测试确认它失败**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py -q -k "built_index or built_assets"`
Expected: FAIL（`/assets/*.js` 现在 404；`/` 发的是旧 `apps/web/index.html`）

- [ ] **Step 7: 改 `routes.py` —— 删掉写死的 `_WEB_ASSETS`**

把

```python
# 前端自己的静态件(app.css / app.js): 零构建, 直接由本服务发出去
_WEB_ASSETS = {"/app.css": "app.css", "/app.js": "app.js"}
```

整段删掉，替换为：

```python
# 前端是构建产物(Vite → apps/web/dist): / 发 index.html, 其余静态件都带哈希落在 /assets/ 下
_DIST_PREFIX = "/assets/"
```

- [ ] **Step 8: 改 `routes.py` 的 GET 分支**

把

```python
        elif p in _WEB_ASSETS:
            self._send_file(_web() / _WEB_ASSETS[p])
        elif p.startswith("/samples/"):
```

改成

```python
        elif p.startswith(_DIST_PREFIX):
            self._serve_static(_web(), p.lstrip("/"))
        elif p.startswith("/samples/"):
```

并把 `/` 与 `/index.html` 那一支的解释补一句（行为不变，`_index()` 已按 LAYOUT 解析到 `dist/index.html`）：

```python
        if p in ("/", "/index.html"):
            # _index() 走 resources.LAYOUT["web"], 现在指 apps/web/dist/index.html
            self._send(200, _index().read_bytes(), "text/html; charset=utf-8")
```

`_serve_static` 已有 `_safe_join` 做穿越防护，直接复用。

- [ ] **Step 9: 跑测试确认通过**

Run: `.venv/bin/python -m pytest packages/docanon-core/tests/test_server.py packages/docanon-core/tests/test_resources.py packages/docanon-core/tests/test_layout.py -q`
Expected: PASS

- [ ] **Step 10: 改 `tests/test_docs.py` 的 `RUNTIME_PREFIXES`**

现状文档（README / architecture）会写 `` `apps/web/dist` ``，那是**构建期才存在**的路径，不该被"路径必须存在"的守卫当成漂移：

```python
RUNTIME_PREFIXES = ("var/", "out/", "website/dist", "apps/web/dist", "apps/desktop/build")
```

- [ ] **Step 11: 跑文档守卫**

Run: `.venv/bin/python -m pytest tests/test_docs.py -q`
Expected: PASS

- [ ] **Step 12: 提交**

```bash
git add packages/docanon-core/src/docanon_core/resources.py \
        packages/docanon-core/src/docanon_core/server/routes.py \
        packages/docanon-core/tests/test_resources.py \
        packages/docanon-core/tests/test_server.py tests/test_docs.py
git commit -m "feat(core): docanon web 改发 apps/web/dist 的构建产物"
```

---

## Task 3: 前端类型与 API 客户端

**Files:**
- Create: `apps/web/src/types.ts`, `apps/web/src/lib/api.ts`

- [ ] **Step 1: 写 `apps/web/src/types.ts`**

与 `routes.py` 的出参**一一对应**（字段名不许改）：

```ts
export type Preset = { name: string; url: string; size: number; preview: boolean };

export type ConfigRow = {
  name: string;
  label: string;
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
  trace?: Trace;
};

export type UploadResp = { token: string; filename: string; url: string };

export type ConfigData = {
  strategies: Record<string, string>;
  detectors: Record<string, boolean>;
  dictionary?: string[];
  onnx?: { model_dirs?: string[] };
  llm?: { base_url?: string; model?: string };
};

export type ConfigDetail = { ref: string; kind: "builtin" | "user"; data: ConfigData };

export type ModelsResp = {
  onnx_dirs: string[];
  llm: { base_url: string; model: string };
};

export type Selection = {
  preset: string | null;
  token: string | null;
  filename: string;
  url: string;
};
```

- [ ] **Step 2: 写 `apps/web/src/lib/api.ts`**

所有网络调用集中在这里；错误统一抛 `Error`（后端返回 `{error}` 时用它当消息），UI 层只管展示。

```ts
import type {
  AnonymizeResp, ConfigData, ConfigDetail, ConfigRow, Detection, ModelsResp, Preset, UploadResp,
} from "../types";

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, { cache: "no-store", ...init });
  const body = (await resp.json()) as T & { error?: string };
  if (body && typeof body === "object" && "error" in body && body.error) {
    throw new Error(body.error);
  }
  return body;
}

const postJson = <T>(url: string, payload: unknown) =>
  json<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const loadPresets = () =>
  json<{ presets: Preset[] }>("/api/presets").then((r) => r.presets);

export const loadConfigs = () =>
  json<{ configs: ConfigRow[] }>("/api/configs").then((r) => r.configs);

export const loadConfigData = (ref: string) =>
  json<ConfigDetail>(`/api/configs/${encodeURIComponent(ref)}`);

export const loadModels = () => json<ModelsResp>("/api/models");

export const uploadFile = (file: File) =>
  fileToBase64(file).then((content_b64) =>
    postJson<UploadResp>("/api/upload", { filename: file.name, content_b64 }),
  );

export const anonymize = (payload: {
  preset?: string; token?: string; config?: string | ConfigData;
}) => postJson<AnonymizeResp>("/api/anonymize", payload);

export const saveConfig = (name: string, data: ConfigData) =>
  json<{ saved: boolean; name: string }>(`/api/configs/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

export const importConfig = (file: File) =>
  fileToBase64(file).then((content_b64) =>
    postJson<{ name: string }>("/api/configs/import", { filename: file.name, content_b64 }),
  );

export const exportConfigUrl = (ref: string) =>
  `/api/configs/${encodeURIComponent(ref)}/export`;

/** File → base64(分块, 避免大文件把栈打爆; 与旧 app.js 同一策略) */
export async function fileToBase64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  let s = "";
  for (let i = 0; i < buf.length; i += 0x8000) {
    s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  }
  return btoa(s);
}

export function totalCounts(counts: Record<string, number> | undefined): number {
  return Object.values(counts ?? {}).reduce((a, b) => a + b, 0);
}

export type { Detection };
```

- [ ] **Step 3: 类型检查 + 构建**

Run: `npm run build -w @doc-anonymizer/web`
Expected: 成功（`tsc --noEmit` 无报错，vite 产出 dist）

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/types.ts apps/web/src/lib/api.ts
git commit -m "feat(web): 后端契约的类型与 typed API 客户端"
```

---

## Task 4: 格式工具与 file-viewer 封装

**Files:**
- Create: `apps/web/src/lib/formats.ts`, `apps/web/src/lib/viewer.ts`

- [ ] **Step 1: 写 `apps/web/src/lib/formats.ts`**

从旧 `app.js` 原样搬（含中文位置文案）：

```ts
export const TEXT_EXT = ["txt", "md", "markdown", "csv"];

export const ENTITY_TYPES = [
  "PHONE", "ID_CARD", "PASSPORT", "PLATE", "BANK_CARD", "EMAIL", "IP", "USCC",
  "PERSON", "ORG", "LOCATION", "AMOUNT", "DOB", "SECRET", "CUSTOM", "DEFAULT",
] as const;

export const STRATEGIES = ["redact", "mask", "placeholder", "pseudonym", "remove", "keep"] as const;

export type Strategy = (typeof STRATEGIES)[number];

/** 每种策略的效果示例(L2 表格里给人看) */
export const EFFECT: Record<string, string> = {
  redact: "**",
  mask: "138****0000",
  placeholder: "<PHONE_1>",
  pseudonym: "林芳",
  remove: "（删除）",
  keep: "（不动）",
};

/** 命中位置 → 人话(与旧 app.js 的 locText 一致) */
export function locText(loc: Record<string, unknown> | undefined): string {
  if (!loc) return "";
  if ("line" in loc) return `第${(loc.line as number) + 1}行`;
  if ("page" in loc) return `第${(loc.page as number) + 1}页${loc.bbox ? "(图)" : ""}`;
  if ("sheet" in loc) return `${loc.sheet}!${loc.cell}`;
  if ("row" in loc) return `r${loc.row}c${loc.col}`;
  if ("paragraph" in loc) return `第${(loc.paragraph as number) + 1}段`;
  return JSON.stringify(loc);
}

export function extOf(filename: string): string {
  return (filename.split(".").pop() || "").toLowerCase();
}
```

- [ ] **Step 2: 写 `apps/web/src/lib/viewer.ts`**

file-viewer 是全局 IIFE，只能命令式挂载；这里封成"一个容器 + 一个 URL"的调用。

```ts
export type ViewerOptions = {
  theme?: string;
  toolbar?: boolean;
  pdf?: { toolbar?: boolean; navigation?: boolean };
};

type FlyfishViewer = {
  setDefaultFullAssetBaseUrl?: (base: string) => void;
  mountViewer?: (
    el: HTMLElement,
    opts: { url: string; filename: string; options?: ViewerOptions },
  ) => void;
};

declare global {
  interface Window {
    FlyfishFileViewerWebFull?: FlyfishViewer;
  }
}

/** 文本类自己渲染(与旧 app.js 的 TEXT_EXT 分支一致) */
async function showText(el: HTMLElement, url: string): Promise<void> {
  try {
    const text = await (await fetch(url)).text();
    const pre = document.createElement("pre");
    pre.className =
      "m-0 h-full overflow-auto whitespace-pre-wrap break-all bg-card p-4 text-[13px] leading-relaxed";
    pre.textContent = text;
    el.replaceChildren(pre);
  } catch (e) {
    el.textContent = `无法预览: ${(e as Error).message}`;
  }
}

/**
 * 把文档挂进 container。文本类走 <pre>，其余交给 file-viewer；
 * file-viewer 挂载失败时回退到文本预览(readable 总比空白强)。
 */
export function mountViewer(container: HTMLElement, url: string, filename: string): void {
  const FV = window.FlyfishFileViewerWebFull;
  if (FV?.setDefaultFullAssetBaseUrl) {
    FV.setDefaultFullAssetBaseUrl(new URL("/file-viewer/", location.href).href);
  }

  const host = document.createElement("div");
  host.className = "absolute inset-0";
  container.replaceChildren(host);

  const ext = (filename.split(".").pop() || "").toLowerCase();
  if (["txt", "md", "markdown", "csv"].includes(ext)) {
    void showText(host, url);
    return;
  }

  if (FV?.mountViewer) {
    try {
      FV.mountViewer(host, {
        url: new URL(url, location.href).href,
        filename,
        // theme 必须放 options 里(顶层会被忽略); pdf.toolbar/navigation 关掉内部工具栏/缩略图,
        // 否则窄窗格横向溢出、re-fit 抖动(与旧 app.js 同因)
        options: { theme: "light", toolbar: false, pdf: { toolbar: false, navigation: false } },
      });
      return;
    } catch (e) {
      console.warn("file-viewer mount failed", e);
    }
  }
  void showText(host, url);
}

export function clearViewer(container: HTMLElement | null): void {
  container?.replaceChildren();
}
```

- [ ] **Step 3: 类型检查 + 构建**

Run: `npm run build -w @doc-anonymizer/web`
Expected: 成功

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/lib/formats.ts apps/web/src/lib/viewer.ts
git commit -m "feat(web): 格式工具与 file-viewer 命令式封装"
```

---

## Task 5: 预览、统计、日志三个展示组件

**Files:**
- Create: `apps/web/src/components/Preview.tsx`, `apps/web/src/components/StatsCard.tsx`, `apps/web/src/components/LogModal.tsx`

- [ ] **Step 1: 写 `apps/web/src/components/Preview.tsx`**

**关键**：`#paneSrc` / `#paneOut` 必须是外层容器的 id，其 `firstElementChild` 是挂载点（E2E 靠这两点找 shadow DOM）。

```tsx
import { useEffect, useRef } from "react";
import { clearViewer, mountViewer } from "../lib/viewer";

type Props = {
  /** "src" | "out": 决定 E2E 依赖的容器 id */
  pane: "src" | "out";
  title: string;
  filename: string;
  url: string;
  placeholder: string;
  action?: { label: string; href: string };
};

export function Preview({ pane, title, filename, url, placeholder, action }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    if (!url) {
      clearViewer(el);
      return () => clearViewer(el);
    }
    mountViewer(el, url, filename);
    return () => clearViewer(el);
  }, [url, filename]);

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card">
      <div className="flex min-h-11 items-center gap-2.5 border-b px-3.5 py-2 text-[13px]">
        <b className="font-semibold">{title}</b>
        <span className="truncate text-muted-foreground">{filename}</span>
        <span className="ml-auto flex gap-2">
          {action && url ? (
            <a href={action.href} download className="inline-flex">
              <span className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
                {action.label}
              </span>
            </a>
          ) : null}
        </span>
      </div>
      <div id={pane === "src" ? "paneSrc" : "paneOut"} className="relative min-h-0 flex-1 overflow-hidden">
        {url ? (
          <div ref={hostRef} className="absolute inset-0" />
        ) : (
          <div className="placeholder absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            {placeholder}
          </div>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 写 `apps/web/src/components/StatsCard.tsx`**

`#stats` 是 E2E 读取节点（`document.getElementById('stats').textContent`），必须是 `<table>`。

```tsx
type Props = { counts: Record<string, number> };

export function StatsCard({ counts }: Props) {
  const entries = Object.entries(counts);
  return (
    <div className="rounded-xl border bg-card p-3.5">
      <h3 className="mb-2.5 text-[13px] font-semibold tracking-wide text-muted-foreground">命中统计</h3>
      <table id="stats" className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="border-b px-2 py-1.5 font-medium">类型</th>
            <th className="border-b px-2 py-1.5 font-medium">数量</th>
          </tr>
        </thead>
        <tbody>
          {entries.length ? (
            entries.map(([k, v]) => (
              <tr key={k}>
                <td className="border-b px-2 py-1.5">{k}</td>
                <td className="border-b px-2 py-1.5 tabular-nums">{v}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={2} className="px-2 py-1.5 text-muted-foreground">未命中</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: 写 `apps/web/src/components/LogModal.tsx`**

保留旧日志的全部信息：口径/检测器/分段耗时/「按配置保留」条数/逐条溯源表。

```tsx
import { locText } from "../lib/formats";
import type { Trace } from "../types";

type Props = { open: boolean; trace: Trace | null; onClose: () => void };

export function LogModal({ open, trace, onClose }: Props) {
  if (!open || !trace) return null;
  const t = trace.timing ?? {};
  const kept = (trace.detections ?? []).filter((d) => d.strategy === "keep");
  const keptCounts: Record<string, number> = {};
  for (const d of kept) keptCounts[d.entity_type] = (keptCounts[d.entity_type] ?? 0) + 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex h-4/5 w-3/4 flex-col overflow-hidden rounded-xl bg-slate-900 text-slate-200 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-3 text-sm">
          <b>运行日志</b>
          <button className="text-xs text-slate-300 hover:text-white" onClick={onClose}>关闭 ✕</button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-3 text-xs leading-relaxed">
          <div className="mb-2 text-slate-400">
            源文件 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.source}</code> · 抽取器{" "}
            <code className="rounded bg-slate-800 px-1.5 py-px">{trace.extractor}</code>
            {trace.converted_from ? (
              <> · 已由 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.converted_from}</code> 转换(版式可能被重排)</>
            ) : null}
            {trace.config ? (
              <> · 口径 <code className="rounded bg-slate-800 px-1.5 py-px">{trace.config}</code></>
            ) : null}
            {" · "}检测器 <code className="rounded bg-slate-800 px-1.5 py-px">{(trace.detectors ?? []).join(" + ")}</code>
            <br />
            耗时: 抽取 {t.extract_ms ?? "-"}ms · 检测 {t.detect_ms ?? "-"}ms · 回写 {t.write_ms ?? "-"}ms · 合计{" "}
            <b>{t.total_ms ?? "-"}ms</b>
            {kept.length ? (
              <>
                <br />按配置保留 <b>{kept.length}</b> 处（
                {Object.entries(keptCounts).map(([k, v]) => `${k}×${v}`).join("、")}）
                —— 识别到了，但这几类不在你的脱敏范围
              </>
            ) : null}
          </div>
          {trace.detections?.length ? (
            <table className="w-full border-collapse">
              <thead>
                <tr className="text-left text-slate-400">
                  {["类型", "来源", "策略", "原文", "", "替换为", "位置"].map((h, i) => (
                    <th key={i} className="border-b border-slate-700 px-2 py-1.5 font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trace.detections.map((d, i) => (
                  <tr key={i} className="align-top">
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.entity_type}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.source}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{d.strategy}</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">
                      <code className="rounded bg-slate-800 px-1.5 py-px">{d.original}</code>
                    </td>
                    <td className="border-b border-slate-700 px-2 py-1.5 text-slate-500">→</td>
                    <td className="border-b border-slate-700 px-2 py-1.5">
                      <code className="rounded bg-slate-800 px-1.5 py-px">
                        {d.strategy === "keep" ? "（保留原样）" : (d.replacement || "（删除）")}
                      </code>
                    </td>
                    <td className="border-b border-slate-700 px-2 py-1.5">{locText(d.locator)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-slate-400">本次未命中任何敏感信息。</div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 类型检查 + 构建**

Run: `npm run build -w @doc-anonymizer/web`
Expected: 成功

- [ ] **Step 5: 提交**

```bash
git add apps/web/src/components/Preview.tsx apps/web/src/components/StatsCard.tsx apps/web/src/components/LogModal.tsx
git commit -m "feat(web): 预览/统计/日志三个展示组件"
```

---

## Task 6: 文档选择与口径面板

**Files:**
- Create: `apps/web/src/components/PresetList.tsx`, `apps/web/src/components/ConfigPanel.tsx`

- [ ] **Step 1: 写 `apps/web/src/components/PresetList.tsx`**

`.preset` 是 E2E 点选钩子（`page.locator('.preset', { hasText: PRESET })`），class 与可选性必须保留。

```tsx
import { Button } from "@doc-anonymizer/ui/primitives/button";
import type { Preset } from "../types";

type Props = {
  presets: Preset[];
  activeName: string | null;
  loading: boolean;
  onPick: (preset: Preset) => void;
  onRefresh: () => void;
  onUpload: (file: File) => void;
  uploading: boolean;
};

export function PresetList({ presets, activeName, loading, onPick, onRefresh, onUpload, uploading }: Props) {
  return (
    <div className="rounded-xl border bg-card p-3.5">
      <div className="mb-2.5 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold tracking-wide text-muted-foreground">选择文档</h3>
        <Button variant="ghost" size="xs" onClick={onRefresh} disabled={loading} title="重新加载 samples/ 里的示例">
          ↻ 刷新示例
        </Button>
      </div>

      {loading ? (
        <div className="text-xs text-muted-foreground">加载中…</div>
      ) : presets.length ? (
        <div className="max-h-56 overflow-auto">
          {presets.map((p) => {
            const active = p.name === activeName;
            return (
              <div
                key={p.name}
                className={`preset mb-1.5 flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-[13px] transition-colors ${
                  active ? "border-primary bg-accent font-semibold text-accent-foreground" : "hover:border-primary/60 hover:bg-accent/60"
                }`}
                title={p.name}
                onClick={() => onPick(p)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onPick(p); }}
              >
                <span aria-hidden>📄</span>
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                <span className="ml-auto text-[11px] uppercase text-muted-foreground">
                  {p.name.split(".").pop()}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">samples/ 无可预览示例</div>
      )}

      <label className="mt-2 block">
        <input
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <Button variant="outline" size="sm" className="w-full" disabled={uploading} asChild={false}>
          {uploading ? "上传中…" : "上传本地文件…"}
        </Button>
      </label>
    </div>
  );
}
```

若 `Button` 不支持用 `label` 包一层触发文件选择，就改成受控写法：组件内 `const fileRef = useRef<HTMLInputElement>(null)`，按钮 `onClick={() => fileRef.current?.click()}`，`<input ref={fileRef} type="file" hidden onChange={...} />`。**以 `npm run build` 通过为准**，两种都行。

- [ ] **Step 2: 写 `apps/web/src/components/ConfigPanel.tsx`**

把 L1（口径选择）/ L2（逐类型策略 + 词典 + 假名开关）/ L3（检测器 + 模型目录 + LLM）用 `Accordion` 收拢；下拉用原生 `<select>`（保 E2E 无关，但交互最稳）。

```tsx
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@doc-anonymizer/ui/primitives/accordion";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { Input } from "@doc-anonymizer/ui/primitives/input";
import { Label } from "@doc-anonymizer/ui/primitives/label";
import { EFFECT, ENTITY_TYPES, STRATEGIES } from "../lib/formats";
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

export function ConfigPanel(props: Props) {
  const { configs, configRef, configData, configKind, modelDirs, onSelectConfig, onChange } = props;
  const d = configData;
  const def = d?.strategies?.DEFAULT ?? "placeholder";

  const setStrategy = (entity: string, value: string) => {
    if (!d) return;
    onChange({ ...d, strategies: { ...d.strategies, [entity]: value } });
  };

  return (
    <div className="rounded-xl border bg-card p-3.5">
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

      <Accordion type="multiple" className="mt-2">
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
                          <td className="border-b px-1.5 py-1">{t}</td>
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
                <Input
                  id="dictInput"
                  className="mt-1 h-8"
                  defaultValue={(d.dictionary ?? []).join("，")}
                  onBlur={(e) => onChange({
                    ...d,
                    dictionary: e.target.value.split(/[，,]/).map((s) => s.trim()).filter(Boolean),
                  })}
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
                  id="llmUrl" className="mt-1 h-8" defaultValue={d.llm?.base_url ?? ""}
                  onBlur={(e) => onChange({ ...d, llm: { ...d.llm, base_url: e.target.value } })}
                />
                <Label className="mt-2 block text-xs text-muted-foreground" htmlFor="llmModel">LLM 模型名</Label>
                <Input
                  id="llmModel" className="mt-1 h-8" defaultValue={d.llm?.model ?? ""}
                  onBlur={(e) => onChange({ ...d, llm: { ...d.llm, model: e.target.value } })}
                />
              </>
            ) : null}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="mt-2 flex gap-1.5">
        <Button variant="outline" size="sm" className="flex-1" onClick={props.onSave}>保存为…</Button>
        <label className="flex-1">
          <input
            type="file" accept=".yaml,.yml" className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) props.onImport(f);
              e.target.value = "";
            }}
          />
          <Button variant="outline" size="sm" className="w-full">导入</Button>
        </label>
        <Button variant="outline" size="sm" className="flex-1" onClick={props.onExport} disabled={!configRef}>
          导出
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 类型检查 + 构建**

Run: `npm run build -w @doc-anonymizer/web`
Expected: 成功。若 `Accordion`/`Button` 的 props 与上面不符（例如 `type="multiple"` 的取值、`size="xs"` 不存在），按 `packages/ui/src/components/ui/accordion.tsx` / `button.tsx` 的实际签名调整——**不要**改 ui 包，也不要拷一份到 app。

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/components/PresetList.tsx apps/web/src/components/ConfigPanel.tsx
git commit -m "feat(web): 文档选择与 L1/L2/L3 口径面板"
```

---

## Task 7: App 组装——布局、暗色、状态与数据流

**Files:**
- Modify: `apps/web/src/App.tsx`（整体重写）

- [ ] **Step 1: 重写 `apps/web/src/App.tsx`**

布局：**左栏**（选择文档 + 口径面板 + 开跑）→ **中**（原文）→ **右**（脱敏后）；窄屏左栏收成抽屉。暗色跟随系统 + 手动切换（`localStorage['docanon.theme']`）。

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@doc-anonymizer/ui/primitives/button";
import { ConfigPanel } from "./components/ConfigPanel";
import { LogModal } from "./components/LogModal";
import { PresetList } from "./components/PresetList";
import { Preview } from "./components/Preview";
import { StatsCard } from "./components/StatsCard";
import * as api from "./lib/api";
import type { AnonymizeResp, ConfigData, ConfigRow, Preset, Selection } from "./types";

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

  const [selection, setSelection] = useState<Selection | null>(null);
  const [result, setResult] = useState<AnonymizeResp | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logOpen, setLogOpen] = useState(false);
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
      const saved = localStorage.getItem("docanon.config");
      const pick = rows.find((c) => c.name === saved) ?? rows.find((c) => c.current) ?? rows[0];
      if (pick) await loadConfigData(pick.name);
    } catch (e) {
      setError(`配置列表加载失败: ${(e as Error).message}`);
    }
  }, [loadConfigData]);

  useEffect(() => { void refreshPresets(); }, [refreshPresets]);
  useEffect(() => { void loadConfigList(); }, [loadConfigList]);
  useEffect(() => {
    api.loadModels().then((m) => setModelDirs(m.onnx_dirs)).catch(() => setModelDirs([]));
  }, []);

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

  const opDetails = useMemo(() => {
    if (!result) return selection ? `已选择: ${selection.filename}` : "未选择文档";
    const types = Object.keys(result.counts ?? {}).join("+") || "无命中";
    const ms = result.trace?.timing?.total_ms;
    const converted = result.trace?.converted_from;
    return `已脱敏 ${result.output_name} · 类型 ${types} · 命中 ${api.totalCounts(result.counts)} · ${
      ms != null ? `${Math.round(ms)}ms` : ""
    }${converted ? ` · 已由 ${converted} 转换, 版式可能被重排` : ""}`;
  }, [result, selection]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="flex flex-none items-baseline gap-3 border-b bg-card px-6 py-3">
        <h1 className="text-lg font-semibold">文档脱敏工具</h1>
        <span className="text-[13px] text-muted-foreground">选文档 → 预览 → 一键脱敏 → 原格式前后对比</span>
        <Button
          variant="ghost" size="xs" className="ml-auto"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          title="切换明暗"
        >
          {theme === "dark" ? "☀ 浅色" : "🌙 深色"}
        </Button>
      </header>

      <div className="flex flex-none items-center gap-2.5 border-b bg-card px-6 py-2">
        <span className="min-w-0 truncate text-xs tabular-nums text-muted-foreground" title={opDetails}>
          {opDetails}
        </span>
        <Button
          variant="ghost" size="xs" className="ml-auto"
          disabled={!result?.trace}
          onClick={() => setLogOpen(true)}
        >
          运行日志
        </Button>
      </div>

      {error ? (
        <div className="mx-6 mt-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 gap-4 p-4">
        {/* 左栏: 宽屏常驻; 窄屏收成抽屉 */}
        <aside
          className={`min-h-0 w-[280px] flex-none space-y-3 overflow-auto md:block ${
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
          <ConfigPanel
            configs={configs}
            configRef={configRef}
            configData={configData}
            configKind={configKind}
            modelDirs={modelDirs}
            onSelectConfig={(name) => void loadConfigData(name)}
            onChange={(next) => { setConfigData(next); setConfigDirty(true); }}
            onSave={() => void saveConfig()}
            onImport={(f) => void importConfig(f)}
            onExport={() => { if (configRef) location.href = api.exportConfigUrl(configRef); }}
          />
          <Button id="run" className="w-full" disabled={!selection || running} onClick={() => void run()}>
            {running ? "脱敏中…" : "开始脱敏"}
          </Button>
          <Button variant="outline" size="sm" className="w-full md:hidden" onClick={() => setDrawerOpen(!drawerOpen)}>
            {drawerOpen ? "收起面板" : "展开面板"}
          </Button>
          {result ? <StatsCard counts={result.counts} /> : null}
        </aside>

        {/* 窄屏唤起抽屉的按钮 */}
        <Button variant="outline" size="sm" className="md:hidden" onClick={() => setDrawerOpen(true)}>
          选择 / 配置
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

      <LogModal open={logOpen} trace={result?.trace ?? null} onClose={() => setLogOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 2: 构建并起后端做端到端自检**

终端 A（后端）: `npm run build:web && .venv/bin/docanon web -p 8000 -c configs/default.yaml`
终端 B: 打开 `http://127.0.0.1:8000/`

逐项确认：
1. 页面有样式（不是裸 HTML）——说明 Tailwind 与 theme.css 生效；
2. 左栏出现 `samples/` 里的示例，点一个 → 中间「原文」出预览；
3. 点「开始脱敏」→ 右侧出结果、左栏出现「命中统计」；
4. 「运行日志」能打开、有关闭按钮；
5. 点右上角切换 → 整页变暗色；
6. 缩窄窗口 → 左栏收起，出现「选择 / 配置」按钮。

- [ ] **Step 3: 跑 WebKit 内核 E2E，确认 DOM 契约没被破坏**

先起一个专用后端（E2E 默认连 8803）:

```bash
npm run build:web && .venv/bin/docanon web -p 8803 -c configs/default.yaml
```

另一个终端:

```bash
cd tests/e2e/webkit && npm install --no-audit --no-fund \
  && DOCANON_URL=http://127.0.0.1:8803 PRESET=sample.docx node webkit-check.mjs
```

Expected: 输出 JSON 里 `before.src.nodes` 与 `after.stats` 非空、`errors` 为空数组。若 `errors` 有内容，先修干净再继续。

- [ ] **Step 4: 提交**

```bash
git add apps/web/src/App.tsx
git commit -m "feat(web): 三栏布局 + 暗色 + React 状态与数据流"
```

---

## Task 8: 开发与分发链路（npm scripts / dev.sh / doctor / check_scope）

**Files:**
- Modify: `package.json`（根 scripts）
- Modify: `scripts/dev.sh`
- Modify: `scripts/check_scope.py`
- Modify: `tests/test_check_scope.py`
- Delete: `apps/web/app.css`, `apps/web/app.js`

- [ ] **Step 1: 删掉旧的零构建三件套残留**

删除 `apps/web/app.css` 与 `apps/web/app.js`（逻辑已全部迁进 `src/`；`index.html` 已重写成 Vite 入口）。

- [ ] **Step 2: 改根 `package.json` 的 scripts**

```json
  "scripts": {
    "setup": "./scripts/dev.sh setup && npm install && npm run build:web",
    "build:web": "npm run build -w @doc-anonymizer/web",
    "dev": "./scripts/dev.sh webui",
    "dev:backend": "./scripts/dev.sh web",
    "dev:website": "./scripts/dev.sh website",
    "dev:desktop": "./scripts/dev.sh desktop",
    "test": "npm run test:py && npm run test:web",
    "test:strict": "npm run build:web && DOCANON_REQUIRE_ENGINES=1 ./scripts/dev.sh test",
    "test:py": "npm run build:web && ./scripts/dev.sh test",
    "test:web": "npm run check -w @doc-anonymizer/ui && npm run build -w @doc-anonymizer/website && npm run build:web",
    "check:scope": "python3 scripts/check_scope.py",
    "build": "npm run build -w @doc-anonymizer/website",
    "cli": "./scripts/dev.sh cli",
    "engines": "./scripts/dev.sh engines",
    "models": "./scripts/dev.sh models",
    "doctor": "./scripts/dev.sh doctor"
  }
```

**为什么 `test:py` 要前置构建**：`packages/docanon-core/tests/test_layout.py` 断言
`resources.web_index().is_file()`，而 `dist` 是 gitignore 的——不先构建，全量 Python 测试在干净检出上必红。

- [ ] **Step 3: `scripts/dev.sh` 加 `webui` 子命令**

在 `cmd_web()` 之后插入：

```bash
# 产品界面的开发态: 后端(docanon web) + Vite dev server 并发跑, Vite 把 /api 等五条前缀代理给后端。
# 生产形态不这样跑 —— 那是 `npm run build:web && ./scripts/dev.sh web`。
cmd_webui() {
  need_venv
  has npm || die "产品界面的开发态要 node/npm: 装 node 后重试(或只起后端: ./scripts/dev.sh web)"
  [ -d node_modules ] || { say "首次: 根目录 npm install(npm workspaces: ui + website + apps/web)…"; npm install --no-audit --no-fund; }

  local port="$DEFAULT_PORT"
  warn_if_no_onnx_models
  say "→ 后端 http://127.0.0.1:$port · 前端 http://127.0.0.1:5173   (Ctrl+C 停止)"

  .venv/bin/docanon web -p "$port" -c "$DEFAULT_CONFIG" &
  local backend_pid=$!
  # 任何退出路径都要收走后端, 否则它孤儿化占住 8000(下次开就报端口被占)
  trap 'kill "$backend_pid" 2>/dev/null || true' EXIT INT TERM
  DOCANON_BACKEND="http://127.0.0.1:$port" npm run dev -w @doc-anonymizer/web
}
```

在 `usage()` 的清单里加一行，并在 `case` 分发里加分支：

```
  webui                产品界面开发态(后端 + Vite dev server + 代理; 生产形态用 web)
```

```bash
  webui) cmd_webui ;;
```

- [ ] **Step 4: `scripts/dev.sh` 的 `doctor` 增加 dist 检查**

在 `== 资产 ==` 段里，`var/vendor/file-viewer` 那一行前后加：

```bash
  if [ -f apps/web/dist/index.html ]; then
    say "  $ok apps/web/dist     产品界面已构建"
  else
    say "  $no apps/web/dist     缺 —— docanon web 起不来; 跑: npm run build:web"
  fi
```

- [ ] **Step 5: `scripts/check_scope.py` 收编产品界面**

把前端组与 MANUAL 改成：

```python
    (
        ("packages/ui/", "apps/web/", "website/", "package.json", "package-lock.json"),
        "前端(共享组件库 / 产品界面 / 官网文档站 / 工作区)",
        [("npm run test:web", "组件库导入规范化检查 + 文档站构建 + 产品界面类型检查与构建")],
    ),
```

```python
MANUAL = {
    "apps/desktop/": "桌面壳: 起 `npm run dev:desktop` 手工验证(需 Hutch)",
}
```

（`apps/web/` 从此有自动化覆盖：`npm run test:web` 里的 `tsc --noEmit` + `vite build`。）

- [ ] **Step 6: `tests/test_check_scope.py` 加一条守卫**

在文件末尾追加：

```python
def test_product_frontend_change_picks_web_checks(repo_root):
    """产品界面现在有自动化覆盖(类型检查 + 构建), 不该再落进"只能手工验证"。"""
    out = _scope(repo_root, "apps/web/src/App.tsx")
    assert "npm run test:web" in out
    assert "手工验证" not in out
```

- [ ] **Step 7: 跑这些检查**

```bash
.venv/bin/python -m pytest tests/test_check_scope.py tests/test_dev_env.py -q
python3 scripts/check_scope.py --files apps/web/src/App.tsx
```

Expected: pytest PASS；`check_scope` 输出建议 `npm run test:web`，且**没有** "手工验证" 一节。

- [ ] **Step 8: 全量验证**

```bash
npm test
```

Expected: `npm run test:py`（含构建）与 `npm run test:web` 全绿。

- [ ] **Step 9: 提交**

```bash
git rm apps/web/app.css apps/web/app.js
git add package.json scripts/dev.sh scripts/check_scope.py tests/test_check_scope.py
git commit -m "chore(web): dev 并发达起 Vite+后端, 产品界面纳入最小检查集"
```

---

## Task 9: 文档同步与决策笔记

**Files:**
- Modify: `README.md`, `README.en.md`, `CONTRIBUTING.md`, `CONTRIBUTING.en.md`
- Modify: `docs/architecture.md`, `docs/architecture.en.md`
- Modify: `AGENTS.md`, `.agent/rules/03-resources.md`, `.agent/rules/07-frontend.md`
- Modify: `packages/ui/README.md`, `website/README.md`, `scripts/README.md`
- Modify: `CHANGELOG.md`
- Create: `.agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md`

- [ ] **Step 1: 同步"零构建"表述（`07-frontend.md`）**

把

```
1. **产品运行期零 node、全离线**：`docanon web` 只发静态文件（现在是零构建的 `apps/web/`：
   `index.html` + `app.css` + `app.js`）。
```

改成

```
1. **产品运行期零 node、全离线**：`docanon web` 只发静态文件（`apps/web/dist/`，
   由 Vite 从 `apps/web/src/` 构建；**运行期不发 node**，构建期用 npm workspaces）。
```

并把目录表里 `| apps/web/ | 产品界面（零构建；将来换栈时引同一个 packages/ui） |` 改成
`| apps/web/ | 产品界面：Vite + React + Tailwind 4，引同一个 packages/ui；产物 dist/ |`。

再加一条 DOM 契约（E2E 依赖，改布局时别动）：

```
- **DOM 契约**：`tests/e2e/webkit/` 按 `.preset` `#run` `#paneSrc` `#paneOut` `#stats` 选择元素 ——
  改界面时这几个钩子（`#paneSrc`/`#paneOut` 的 `firstElementChild` 是预览挂载点）不许改名或挪位置。
- 加前端依赖/改构建：`npm run build:web`；dev 态 `npm run dev`（后端 + Vite 并发 + 五条前缀代理），
  生产形态 `npm run build:web && npm run dev:backend`。
```

注意：`.agent/rules/07-frontend.md` 有 **≤ 60 行**的硬上限（`tests/test_docs.py::test_agent_rules_stay_small_and_indexed`）。
现状 47 行，上面这几条加完约 54 行——紧，但够。若超了，把"加前端依赖/改构建"那两条并进上面的目录表描述里。

- [ ] **Step 2: 同步 `03-resources.md` 与 `AGENTS.md`**

`03-resources.md` 第 4 行把 `apps/web/` 的举例改成 `apps/web/dist/`（它现在由 LAYOUT 指向）。
根 `AGENTS.md` 第 4 行把 `零构建产品前端（`apps/web/`）` 改成 `产品前端（`apps/web/`，Vite+React，产物 dist/）`。
注意 `AGENTS.md` 必须仍然 ≤ 80 行。

- [ ] **Step 3: 同步 `README.md` 的接口清单与命令表**

- 命令表加两行：

```
| `npm run build:web` | 构建产品界面 → `apps/web/dist/`（`docanon web` 发它） |
| `npm run dev:backend` | 只起后端（发已构建的 dist；验证生产形态） |
```

- 接口那行的 `/app.css` `/app.js` 改成 `/assets/*`：

```
接口：`/` `/assets/*` `/health` `/api/presets` `/api/configs` …（其余不变）
```

- 快速上手那段把 `npm run dev` 的说明补成"后端 + Vite dev（热更）"，并注明生产形态是
  `npm run build:web && npm run dev:backend`。

- [ ] **Step 4: 同步 `README.en.md` 的同一处**

英文版按同样两处改（接口行的 `/app.css` `/app.js` → `/assets/*`；npm scripts 表补 `build:web` / `dev:backend`）。
改完必须跑 `python3 website/scripts/sync-content.py --record-hashes` 刷新译文基线（否则
`test_bilingual_pages_are_paired_and_fresh` 会红）。

- [ ] **Step 5: 同步 `docs/architecture.md` / `.en.md`**

- 目录树行 `│   ├── web/             产品前端(零构建): index.html + app.css + app.js, docanon web 直接发`
  改成 `│   ├── web/             产品前端(Vite+React): src/ 源码 → dist/ 产物, docanon web 发 dist/`；
- 决策表里"前端零构建、三个静态件"那一行改成"前端改 Vite + React + TS（构建期 node，运行期零 node）"，
  理由写"复用 `packages/ui`（换栈不换外观）、有真类型检查与打包压缩"，代价写"多一条构建链与 dist 前置依赖"。

- [ ] **Step 6: 同步 `CONTRIBUTING.md` / `.en.md`、`packages/ui/README.md`、`website/README.md`、`scripts/README.md`**

- `CONTRIBUTING*.md` "前端有两条路径"段：`apps/web/` 不再"零构建"，改成"Vite 构建，产物 dist 由 docanon web 发"。
- `packages/ui/README.md`："将来产品前端换栈时也引它" → "产品前端（`apps/web`）现在就在引它"。
- `website/README.md` 同类表述同步。
- `scripts/README.md`：`dev.sh` 那行补上 `webui` 子命令。

- [ ] **Step 7: 写决策笔记（DSH 两轴格式）**

新建 `.agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md`：

```markdown
# Agent Note: 产品前端从零构建迁到 Vite + React

Status: implemented
Date: 2026-10-09

## 问题

`apps/web/` 是零构建的手写件（`index.html` + `app.css` 68 行 + `app.js` 373 行），功能齐但视觉是裸样式；
而仓库里 `@doc-anonymizer/ui`（velora 100 组件 + shadcn 基础件 + 设计 token）只有 `website/` 在用。
"组件抽成共享包"当初的理由就是"产品前端换栈时引同一个包，外观不会分叉" —— 那个换栈时机就是现在。

## 决策

产品界面迁到 **Vite 5 + React 19 + TS + Tailwind 4**，`import` 同一个 `@doc-anonymizer/ui`。
产物落 `apps/web/dist`（gitignore），`resources.LAYOUT["web"]` 改指 `dist`；服务端只改静态映射，API 一字不改。

## 代价与取舍

- **多一条构建链**：`npm run setup` 要先构建；`test:py` 前置 `build:web`（`test_layout.py` 要求
  `dist/index.html` 存在）。换来的是真类型检查、打包压缩与组件复用。
- **运行期仍然零 node**：`docanon web` 还是只发静态文件，离线语义没变。
- **选了 `dist/` 而不是"构建到 apps/web/ 根"**：Vite 的入口模板与产物同名 `index.html`，
  输出到项目根会自我覆盖、`emptyOutDir` 还有清空源码的风险。
- **保留 DOM 契约**（`.preset` `#run` `#paneSrc` `#paneOut` `#stats`）：E2E 按这些选择器跑，
  换框架不能顺手改名。

## 证据

- 设计：`docs/specs/2026-10-09-web-ui-vite-migration-design.md`
- 守卫：`packages/docanon-core/tests/test_{layout,resources,server}.py`、`tests/test_check_scope.py`
- 契约：`tests/e2e/webkit/{webkit-check,jitter-check}.mjs`
```

- [ ] **Step 8: 更新 `CHANGELOG.md`**

在 `## [Unreleased]` 的 `### Changed` 下追加：

```markdown
- **产品界面重写为 Vite + React + TS**：`apps/web/` 从零构建手写件（`index.html`+`app.css`+`app.js`）
  迁到 Vite 5 + React 19 + Tailwind 4，**复用**共享组件库 `@doc-anonymizer/ui`（velora + shadcn 基础件 +
  设计 token）—— 外观与官网不再分叉。顺带重排为三栏（左栏配置渐进披露、中原文、右脱敏后）、补暗色与
  空/加载态。产物落 `apps/web/dist`（gitignore），`resources.LAYOUT["web"]` 随之改指 `dist`，
  `docanon web` 仍只发静态文件（**运行期零 node、全离线**不变）；API 一字未改。
  新增 `npm run build:web` / `dev:backend`，`npm run dev` 改为"后端 + Vite dev server 并发 + 五条前缀代理"。
  设计与决策：[设计](docs/specs/2026-10-09-web-ui-vite-migration-design.md) ·
  [笔记](.agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md)。
```

- [ ] **Step 9: 跑文档守卫（会连带查路径/链接/单一出处/译文基线）**

```bash
.venv/bin/python -m pytest tests/test_docs.py -q
```

Expected: PASS。红在哪就按提示改：路径不存在 → 补 `RUNTIME_PREFIXES` 或改文档；
译文基线不符 → 跑 `python3 website/scripts/sync-content.py --record-hashes`。

- [ ] **Step 10: 提交**

```bash
git add README.md README.en.md CONTRIBUTING.md CONTRIBUTING.en.md \
        docs/architecture.md docs/architecture.en.md AGENTS.md \
        .agent/rules/03-resources.md .agent/rules/07-frontend.md \
        packages/ui/README.md website/README.md scripts/README.md \
        CHANGELOG.md website/content-manifest.json \
        .agent/notes/implemented/architecture/2026-10-09-product-frontend-on-vite.md
git commit -m "docs: 产品界面迁移到 Vite + React 的说明、规则与决策笔记"
```

---

## 最终验收

- [ ] `npm run setup` 在干净检出上能装齐并产出 `apps/web/dist/index.html`
- [ ] `npm run doctor` 报告 `apps/web/dist` 为 ✓
- [ ] `npm test` 全绿（Python 全量 + 组件库检查 + 文档站构建 + 产品界面类型检查与构建）
- [ ] `npm run check:scope -- --files apps/web/src/App.tsx` 建议 `npm run test:web`，且无"手工验证"
- [ ] `npm run dev` 起得来，浏览器 5173 上界面有样式、能脱敏、能看日志、能切暗色
- [ ] WebKit E2E（`tests/e2e/webkit/webkit-check.mjs`）控制台无 error
- [ ] 装了模型后 `npm run test:strict` 无 skip（反假绿）

## 自检记录

- **Spec 覆盖**：目标/非目标 → Task 1–9；目录与构建（`apps/web/dist`）→ Task 1、2；服务端改动 → Task 2；
  组件与视觉（只 import、`@source`、布局优化、暗色、DOM 契约）→ Task 1、6、7；数据流与状态 → Task 3、7；
  兼容性契约（API 一字不改）→ Task 3 的类型与 Task 2 的测试；开发与分发 → Task 8；
  错误处理（不许静默少一层）→ 沿用后端 400+原因，前端统一错误条（Task 7 的 `error` 态）；
  测试与守卫 → Task 2、8；风险与缓解 → Task 2（`RUNTIME_PREFIXES`）、Task 8（check_scope/doctor）、
  Task 7（E2E）。
- **占位符扫描**：无 TBD/TODO；每个改码步骤都给了完整代码与期望输出。
- **类型一致性**：`ConfigData` / `Trace` / `AnonymizeResp` / `Selection` / `Preset` 在 Task 3 定义，
  Task 5–7 使用同名同形；`api.ts` 导出名（`loadPresets`/`loadConfigData`/`loadModels`/`uploadFile`/
  `anonymize`/`saveConfig`/`importConfig`/`exportConfigUrl`/`totalCounts`）在 Task 7 一致引用。
- **实测过的前提**（不是推测）：`packages/ui` 的依赖（motion / @base-ui/react / cn / lucide-react /
  class-variance-authority / tw-animate-css / react / react-dom）都已在 `node_modules` 里；
  `npx tsc --noEmit -p packages/ui/tsconfig.json` 的报错**只**出现在 3 个 `blocks/` 文件里，
  `primitives/` 干净 —— 这是"apps/web 只许 import primitives"这条约束的依据。
- **未验证的部分**：`vite@^5` / `@vitejs/plugin-react@^4` / `@tailwindcss/vite@^4` 的版本能解出兼容组合
  （离线无法预检），所以 Task 1 Step 8 把"`npm install` 成功 + 出 `dist`"当成显式关卡而不是走过场。
