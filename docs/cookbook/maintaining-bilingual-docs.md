# 维护双语文档

**产品层文档必须有英文版**：`README.md`、`docs/quickstart.md`、`docs/architecture.md`、`CONTRIBUTING.md`
（各有 `<名字>.en.md`）。开发内部文档（`.agent/**`、`docs/cookbook`、包说明）目前仅中文 —— 英文站对它们
用中文内容回退，不 404。

## 改一篇已有中文的文档

1. 改中文源（例如 `docs/quickstart.md`）。
2. **同一提交里改英文版** `docs/quickstart.en.md`，保持结构一致：标题层级与顺序、表格行列数、
   代码块内容（命令/路径/配置键一律不译，只译注释文字）。
3. 刷新译文基线——不刷的话门禁会认为"中文改了英文没跟"：

   ```bash
   python3 website/scripts/sync-content.py --record-hashes
   ```

4. 跑门禁并确认英文页真的变了（不要只看构建成功）：

   ```bash
   .venv/bin/python -m pytest tests/test_docs.py -q        # 配对 + 哈希 + 切换入口
   npm run build && ls website/dist/en/start/quickstart/   # 英文路由真的产出
   ```

## 加一篇新的双语页

1. 写中文源 + `<名字>.en.md`（带互相切换的行）。
2. 在 `website/content-manifest.json` 的那一页上补 `"en": "<英文源路径>"` 与 `"en_title": "<英文标题，侧栏用>"`。
3. 跑 `--record-hashes` 与上面的验证。**必须进 `BILINGUAL_REQUIRED` 的只有那四篇产品层文档**，
   其余页面加不加英文由你决定（加了就要按上面的规矩维护）。

## 语言怎么落到站点上

- 中文在根路径，英文在 `/en/`（`website/astro.config.mjs` 的 `locales`：`root` + `en`）。
- 侧栏由 `sync-content.py` 生成时带 `translations`（中英标签各一份），页面 slug 两种语言共用。
- 缺译文的页面由 Starlight 的 fallback 路由承接：`/en/<页面>/` 会渲染中文内容而不是 404。
- 站内链接一律走 `url()`（子路径部署才不会 404），见 `docs/cookbook/shipping-the-website.md`。
