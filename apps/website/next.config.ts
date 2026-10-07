import type { NextConfig } from "next";

// 部署到子路径(如 GitHub Pages 的项目页)时: NEXT_PUBLIC_BASE_PATH=/doc-anonymizer npm run build
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  // 静态导出: 构建出 out/, 交给任意静态服务器(或 Pages)直接发 —— 运行期不需要 node
  output: "export",
  // 工作区里的 @doc-anonymizer/ui 直接发 TS 源码, 需要 Next 帮忙转译
  transpilePackages: ["@doc-anonymizer/ui"],
  basePath,
  images: { unoptimized: true },
  // 目录式输出(docs/quickstart/index.html): 任何静态服务器(含 python -m http.server)都能直接访问,
  // 不依赖托管方的"省略扩展名"规则
  trailingSlash: true,
  // ⚠️ 别开 cacheComponents / PPR: 与 output: "export" 不兼容,
  //    构建会以 "Invariant: PPR cannot be enabled in export mode" 直接失败
  turbopack: { rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } } },
};

export default nextConfig;
