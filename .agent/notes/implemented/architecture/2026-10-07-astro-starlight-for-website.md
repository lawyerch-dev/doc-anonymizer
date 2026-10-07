# Agent Note: 网站选 Astro + Starlight，而不是 Next.js

Status: implemented

## 问题

`website/` 是「产品落地页 + 文档站」。先按 velora 的形状（shadcn/Next）用 Next 16 做了一版，功能能跑，
但**文档站该有的东西全要自己写**：搜索、TOC、上下页、多语言、版本化。而集成前并没有做过框架评估 ——
是用户追问"你还没评估过用 next 是好还是坏呢"才补的对比。

## 实测对比

同条件（各自独立安装的 app、同样读仓库 markdown、同样用 velora 组件）：

| | Astro + Starlight | Next.js（先试的那版） |
|---|---|---|
| 依赖体积（app 自己的 node_modules） | 241 M | 537 M |
| 构建 | 0.7 s（整站 4 s 含索引） | 3–4 s |
| 产物 | 1.2–1.8 M | 2.0 M |
| 搜索 / TOC / 上下页 / i18n | **内置**（Pagefind 索引 10 页 / 1672 词） | 要自己写 |
| velora 组件 | 可用（React island，实测进静态 HTML） | 原生 |
| 读仓库外部 markdown | 可用（同步脚本） | 可用（构建期 `fs` 读） |

## 决策

网站用 **Astro 5 + Starlight**；产品前端（`apps/web`）将来换栈时引**同一个 `apps/ui`**，
所以网站用什么框架不会让外观分叉。代价：仓库里可能有两个前端框架（组件仍共享）。

顺带定下的机制：内容由 `website/content-manifest.json` → `website/scripts/sync-content.py` 生成
（Starlight 要 frontmatter，仓库文档是给人读的纯 markdown）；生成物 gitignore，**源始终是仓库那些 `.md`**；
侧栏由同一份清单生成，不在 `astro.config.mjs` 里抄第二份。

## 证据

- 构建：`npm run build` → 22+ 页静态输出；`/`、`/start/*`、`/dev/*`、`/agent/*` 全 200（`python -m http.server` 直接发 `dist/`）。
- 搜索：WebKit 打开 `⌘K` 搜「脱敏」得到 6 条结果，零控制台错误。
- 对比数字来自 `/tmp` 里的两个探针对照跑（口径写在 `website/README.md`）。

## 影响与代价

- 站点构建不再需要"配置静态导出"，默认就是静态输出。
- 将来产品前端若选 React/Next，仓库会有两套构建链（组件共享，外观不分叉）。
