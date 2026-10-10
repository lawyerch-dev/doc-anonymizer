# 环境与可再生资产

- **可再生资产都在 `var/`**：`models`（权重）、`vendor`（file-viewer 预览包）、`out`（默认产物）、
  `pycache`（字节码缓存）。gitignore 一条 `var/` 覆盖。
  两处例外，都是**打包输入**而不是运行期资产：壳的 `apps/desktop/build/`（Hutch 的 `buildFolder`
  只接受项目相对路径、不许 `..` 跳出）与 `apps/desktop/stage/`（`copy` 只认本项目内的路径，
  所以 `dev.sh dist` 先把资源根摆到这里）。另外 `apps/desktop/icon.iconset/` 是**提交**的，
  因为生成它要 `rsvg-convert`（不是每台机器都有）。
- **字节码缓存只有一处**：`var/pycache`（`scripts/setup_dev.sh` 往 venv 装 sitecustomize 重定向）。
  源码树里不该出现 `__pycache__`，`tests/test_dev_env.py` 盯着。
  **不要改成一概不写字节码**：实测那样每次要重编译所有导入，整套测试 5.12s → 6.24s。
- `samples/` 由 `scripts/make_samples.py` 生成，不要手改。重新生成的 PDF 必须内嵌中文 TTF 子集
  （脚本取 macOS 的 `Arial Unicode.ttf`）；非嵌入 CID 字体会让 file-viewer 中文预览乱码（commit `094b863`）。
- 干净环境起 Web 前先 `./scripts/fetch_file_viewer.sh`；`var/vendor/`（232MB）缺了时预览区
  所有 `/file-viewer/*` 请求 404。
- Web 后端关掉了 HTTP 访问日志（`docanon_core/server/routes.py` 的 `log_message` 是空实现）；
  命中溯源看 `/api/anonymize` 返回的 `trace`（`extractor`/`detectors`/`timing`/`detections`）。
- 桌面壳（`apps/desktop/`，Electrobun）日常不碰，**只有要发安装包时才碰**。六条实测约束：
  项目根靠标记文件向上找（不许数 `..`，dev 产物在包内）、sidecar 由 `DOCANON_EXIT_WITH_PARENT`
  父进程监视自尽（壳被强杀时 JS 收不了尸；Windows 没有 reparent，那边用 `OpenProcess` 探活）、
  `/health` 带 pid 以免认错端口上的旧孤儿、侧车用 **onedir 不用 onefile**（onefile 的引导器会 fork，
  pid 对不上就被当成"端口被占"）、**必须在各自系统上打**（hutch 是分平台原生二进制，PyInstaller
  不做交叉编译；只发 Apple Silicon——没有 `macos-x64` 产物）、OCR 权重得在打包前下好
  （rapidocr 默认是运行时下到 `site-packages` 的）。细节见 `apps/desktop/README.md`。
  打包入口 `npm run dist:desktop`（= `scripts/dev.sh dist`，两个平台同一条），
  CI 矩阵见 `.github/workflows/build-desktop.yml`。壳的行为由
  `packages/docanon-core/tests/test_server.py` 锁定（含 Windows 那条，在 mac 上按"平台不适用"跳过）。
