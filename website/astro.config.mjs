import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import react from "@astrojs/react";
import tailwindcss from "@tailwindcss/vite";
import sidebar from "./src/sidebar.generated.mjs";

// 部署到子路径(如 GitHub Pages 项目页)时: SITE_BASE=/doc-anonymizer npm run build
const base = process.env.SITE_BASE || "/";
// 部署时给 SITE_URL(如 https://lawyerch-dev.github.io); 不给就跳过 sitemap
const site = process.env.SITE_URL || undefined;

export default defineConfig({
  // 静态站: dist/ 交给任意静态服务器, 运行期不需要 node
  output: "static",
  base,
  site,
  integrations: [
    starlight({
      title: "doc-anonymizer",
      description: "本地文档脱敏：中文优先、全离线、保留原格式",
      defaultLocale: "root",
      locales: { root: { label: "简体中文", lang: "zh-CN" } },
      // 侧栏由 scripts/sync-content.py 从 content-manifest.json 生成(不要在这里手写第二份)
      sidebar,
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/lawyerch-dev/doc-anonymizer" }],
      customCss: ["./src/styles/global.css"],
      // 页面内组件用得到 velora 的动效, 由 React island 承载
      components: {},
    }),
    react(),
  ],
  vite: { plugins: [tailwindcss()] },
});
