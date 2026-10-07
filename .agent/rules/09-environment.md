# 环境与可再生资产

- **可再生资产都在 `var/`**：`models`（权重）、`vendor`（file-viewer 预览包）、`out`（默认产物）、
  `pycache`（字节码缓存）。gitignore 一条 `var/` 覆盖。
  唯一例外是壳的 `apps/desktop/build/`：Hutch 的 `buildFolder` 只接受项目相对路径、不许 `..` 跳出。
- **字节码缓存只有一处**：`var/pycache`（`scripts/setup_dev.sh` 往 venv 装 sitecustomize 重定向）。
  源码树里不该出现 `__pycache__`，`tests/test_dev_env.py` 盯着。
  **不要改成一概不写字节码**：实测那样每次要重编译所有导入，整套测试 5.12s → 6.24s。
- `samples/` 由 `scripts/make_samples.py` 生成，不要手改。重新生成的 PDF 必须内嵌中文 TTF 子集
  （脚本取 macOS 的 `Arial Unicode.ttf`）；非嵌入 CID 字体会让 file-viewer 中文预览乱码（commit `094b863`）。
- 干净环境起 Web 前先 `./scripts/fetch_file_viewer.sh`；`var/vendor/`（232MB）缺了时预览区
  所有 `/file-viewer/*` 请求 404。
- Web 后端关掉了 HTTP 访问日志（`docanon_core/server/routes.py` 的 `log_message` 是空实现）；
  命中溯源看 `/api/anonymize` 返回的 `trace`（`extractor`/`detectors`/`timing`/`detections`）。
- 桌面壳（`apps/desktop/`，Electrobun）只在 `hutch electrobun dev` 里跑，日常不碰。三条实测约束：
  项目根靠标记文件向上找（不许数 `..`，dev 产物在 `.app` 里）、sidecar 由 `DOCANON_EXIT_WITH_PARENT`
  父进程监视自尽（壳被强杀时 JS 收不了尸）、`/health` 带 pid 以免认错端口上的旧孤儿。
  细节见 `apps/desktop/README.md`，行为由 `packages/docanon-core/tests/test_server.py` 锁定。
