# 排查问题：从症状到根因

先按症状跑对的那一条，别猜。命令都贴输出，定位到根因再改。

| 症状 | 先跑什么 | 看什么 |
|---|---|---|
| 漏脱敏 / 引擎起不来 / 跑一半退 | `npm run doctor`、`npm run engines` | 每层的"可用"与原因；缺模型、缺依赖、配置没启用 |
| 跑完没有产物 / 只处理了一部分 | `cat var/out/manifest.json` | 每个文件的 `status`（`ok`/`error`/`unsupported`）与错误原文 |
| 还原对不上 | `cat var/out/mapping.json` | `strategy: remove` 的条目**不可还原**（见[笔记](../../.agent/notes/implemented/bug-fix/2026-10-06-restore-empty-string.md)） |
| 网页显示不对（数字重复/背景透明） | 浏览器控制台 + 计算样式 | Tailwind 类名有没有被生成（`@source` 指错会静默摇掉；[复盘](../../.agent/postmortem/0001-tailwind-source-dropped-classes.md)） |
| 网站构建失败 | `npm run build` | 第一条 error：Starlight 对 frontmatter/侧栏最挑 |
| 子路径部署后 404 | 打开 `/doc-anonymizer/…` | 站内链接是不是写死了 `href="/…"`（要走 `url()`） |
| PDF 涂黑了还能复制 | `python -c "…"` 抽文字，或 `pdftotext` | 命中页必须**整页栅格化**，不许留文字层 |

1. **先复现**：用最小输入（`samples/` 里挑一个文件或一份构造的）跑出同样的症状。
2. **再定位**：按上表跑到"谁报的错/谁没报错"。**没报错的地方就是嫌疑点** —— 本仓库的契约是
   「少一层必须报错」，静默就是 bug。
3. **修根因**：不要在下游加兜底绕过上游的错（那会把错误变成静默）。
4. **留证据**：把根因和证据写进 [`.agent/notes/`](../../.agent/notes/README.md)（类型 `bug-fix`），
   并从对应规则/架构表链接过去。
5. **补门禁**：能写成检查的就写成检查（`tests/`），否则它还会再犯一次。
