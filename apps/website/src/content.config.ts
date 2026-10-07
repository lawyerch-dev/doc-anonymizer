import { defineCollection, z } from "astro:content";
import { docsLoader } from "@astrojs/starlight/loaders";
import { docsSchema } from "@astrojs/starlight/schema";

// 内容由 scripts/sync-content.py 从仓库里的 markdown 同步进来(构建产物, 不提交) —— 源始终是仓库那些 .md
export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
