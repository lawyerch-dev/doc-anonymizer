import fs from "node:fs";
import path from "node:path";

/** 仓库根 = apps/website/../..  */
export const REPO_ROOT = path.resolve(process.cwd(), "..", "..");

export type DocEntry = {
  /** URL 片段, 例如 "quickstart" 或 "architecture" */
  slug: string;
  /** 侧栏显示名 */
  title: string;
  /** 仓库相对路径 */
  file: string;
  /** 侧栏分组 */
  group: string;
  /** 一句话说明 */
  summary: string;
};

/**
 * 文档站展示哪些文件、怎么分组 —— 这里是唯一清单。
 * 只列"现状权威 + 记录类"的面向人文档; AGENTS/specs 那些开发契约也放"开发"组里,
 * 因为改代码的人同样需要它们。
 */
export const DOCS: DocEntry[] = [
  { slug: "quickstart", title: "快速上手", group: "开始", file: "docs/quickstart.md", summary: "5 分钟跑通 + 常见问题" },
  { slug: "readme", title: "使用手册", group: "开始", file: "README.md", summary: "命令、产物、配置、引擎与已知限制" },
  { slug: "contributing", title: "贡献指南", group: "开发", file: "CONTRIBUTING.md", summary: "环境、测试、提交与 PR" },
  { slug: "agents", title: "开发契约", group: "开发", file: "AGENTS.md", summary: "不能违反的边界、命令与坑" },
  { slug: "architecture", title: "架构与目录设计", group: "开发", file: "docs/architecture.md", summary: "五包结构、硬边界、决策记录" },
  { slug: "benchmarks", title: "选型与基准", group: "开发", file: "docs/benchmarks.md", summary: "ONNX / LLM 各模型实测数字" },
  { slug: "scripts", title: "脚本清单", group: "开发", file: "scripts/README.md", summary: "每个脚本干什么、怎么调" },
  { slug: "desktop", title: "桌面壳", group: "开发", file: "apps/desktop/README.md", summary: "Electrobun 壳的运行方式与三条约束" },
  { slug: "security", title: "安全策略", group: "其他", file: "SECURITY.md", summary: "漏脱敏怎么报、设计上的边界" },
  { slug: "changelog", title: "更新日志", group: "其他", file: "CHANGELOG.md", summary: "版本变更" },
];

export function readDoc(entry: DocEntry): string {
  const md = fs.readFileSync(path.join(REPO_ROOT, entry.file), "utf-8");
  // 去掉正文里的一级标题: 页面顶部已经渲染了 doc.title
  return md.replace(/^#\s+.*\n+/, "");
}

/** markdown 里的相对链接要改写成站内路由(否则点过去 404) */
export function rewriteLinks(md: string, current: DocEntry): string {
  const byFile = new Map(DOCS.map((d) => [d.file, d]));
  return md.replace(/\]\(([^)\s]+)\)/g, (whole, href: string) => {
    if (/^(https?:|mailto:|#)/.test(href)) return whole;
    const [target, hash = ""] = href.split("#");
    if (!target.endsWith(".md")) return whole;
    const resolved = path
      .relative(REPO_ROOT, path.resolve(REPO_ROOT, path.dirname(current.file), target))
      .split(path.sep)
      .join("/");
    const hit = byFile.get(resolved);
    return hit ? `](/docs/${hit.slug}${hash ? `#${hash}` : ""})` : whole;
  });
}

/** 侧栏分组顺序 */
export function groupedDocs(): { group: string; items: DocEntry[] }[] {
  const order = ["开始", "开发", "其他"];
  return order
    .map((group) => ({ group, items: DOCS.filter((d) => d.group === group) }))
    .filter((g) => g.items.length > 0);
}
