---
name: cut-a-release
description: Use when publishing a version: bumping versions, updating the changelog, tagging, and checking the website build.
---

# 发一个版本

1. 版本号：五个 `packages/*/pyproject.toml`（`version`）、`website/package.json`、`packages/ui/package.json`
   保持一致（语义化版本）。
2. `CHANGELOG.md`：把 `[Unreleased]` 的内容落到 `## [x.y.z] — YYYY-MM-DD`，并留一个空的 `[Unreleased]`。
3. 全量验证（必须真跑，贴结果）：

```bash
npm test                     # pytest + 组件库 check + 文档站构建
npm run doctor               # 环境自检
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml   # CLI 端到端（11/11 ok）
```

4. 打 tag 并推送：`git tag -a vX.Y.Z -m "..." && git push --tags`（远程没配就先 `git remote add`）。
5. 网站部署：`SITE_BASE=… SITE_URL=… npm run build` 后把 `website/dist/` 发到静态托管。

**别做**：不要在没有验证的情况下声称"已发布"；`mapping.json` 与 `var/` 之类的东西绝不入库。
