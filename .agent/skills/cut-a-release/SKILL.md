---
name: cut-a-release
description: Use when publishing a version: bumping versions, updating the changelog, tagging, and checking the website build.
---

# 发一个版本

1. 版本号：五个 `packages/*/pyproject.toml`（`version`）、`packages/docanon-core/src/docanon_core/__init__.py`
   的 `__version__`、`website/package.json`、`packages/ui/package.json` 保持一致（语义化版本）。
   改了 `website/` 与 `packages/ui/` 的版本要跟着跑一次 `npm install --package-lock-only`
   （lock 里记着各 workspace 的版本，不同步 `npm ci` 会报不一致）。`apps/*` 与 `tests/e2e/*` 是私有 app，
   不参与版本同步。
2. `CHANGELOG.md`：把 `[Unreleased]` 的内容落到 `## [x.y.z] — YYYY-MM-DD`，并留一个空的 `[Unreleased]`。
3. 全量验证（必须真跑，贴结果）：

```bash
npm test                     # pytest + 组件库 check + 文档站构建
npm run doctor               # 环境自检
.venv/bin/docanon run ./samples -o var/out -c configs/onnx.yaml   # CLI 端到端（11/11 ok）
```

4. 打 tag 并推送：`git tag -a vX.Y.Z -m "..." && git push --tags`（远程没配就先 `git remote add`）。
   **这一步会自动出安装包**：`.github/workflows/build-desktop.yml` 在 macOS 与 Windows 的 runner 上
   各打一份并传到 Release —— 用户下载的是 `macos-arm64-doc-anonymizer.dmg` 与
   `win-x64-doc-anonymizer-Setup.zip`（**zip 里才是 `Setup.exe`**，文件名别在 Release 说明里写错）。
   打不出来会红在 Actions 里 —— 那就是"这次发布没完成"。
   （要先试跑又不打 tag：Actions 里手动 `workflow_dispatch`，产物留在该次 run 的 artifact 里。）
5. 网站部署：`SITE_BASE=… SITE_URL=… npm run build` 后把 `website/dist/` 发到静态托管。

**别做**：不要在没有验证的情况下声称"已发布"；`mapping.json` 与 `var/` 之类的东西绝不入库。
**记得写**：Release 资产**不签名不公证** —— macOS 用户首次要右键→「打开」，Windows 首次要
「更多信息」→「仍要运行」；在 Release 说明里说清楚，别让人以为文件下坏了。
