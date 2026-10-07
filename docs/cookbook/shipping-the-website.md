# 构建与部署网站/文档站

1. **本地开发**：`npm run dev:website` → <http://127.0.0.1:4321>。
   内容来自仓库里的 markdown（清单 `website/content-manifest.json`），改完会自动同步；不要手改生成物。
2. **本地构建**：

   ```bash
   npm run build           # → website/dist/（根路径部署）
   ```

3. **子路径部署**（GitHub Pages 项目页必须）：`base` 由 `SITE_BASE` 决定，`site`（sitemap）由 `SITE_URL` 决定：

   ```bash
   SITE_BASE=/doc-anonymizer SITE_URL=https://lawyerch-dev.github.io npm run build
   ```

   验证子路径真的成立（不是只看构建成功）：

   ```bash
   rm -rf /tmp/pages && mkdir -p /tmp/pages
   cp -r website/dist /tmp/pages/doc-anonymizer
   python3 -m http.server -d /tmp/pages 8080     # 打开 http://127.0.0.1:8080/doc-anonymizer/
   ```

4. **自动部署**：`.github/workflows/deploy-website.yml` —— push 到 `main`（或手动触发）时先过门禁再发布
   GitHub Pages。CI 跑的是**部署相关的那部分**（文档漂移 + 包边界 + 组件库导入检查 + 带 `SITE_BASE` 的站点构建），
   **不是全量**：引擎测试需要模型与重依赖，它们的门禁是本地 `npm test`（提交前自己跑）。
   仓库 Settings → Pages → Source 选 **GitHub Actions**（只需设置一次）。
5. **站内链接必须走 `url()`**（`website/src/lib/site.ts`）：手写 `href="/…"` 在子路径下会 404，
   有守卫拦（`tests/test_docs.py`）。Starlight 自己生成的链接（侧栏/搜索/TOC）会跟着 `base` 走。
