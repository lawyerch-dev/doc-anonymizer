# Agent Note: 桌面壳从 Electrobun 换回 Tauri v2

Status: implemented
Date: 2026-10-10
Deciders: 项目作者（陈恒律师）

## 问题

桌面壳换过四轮：Electron → Tauri（因 WKWebView 下 PDF 预览抖动被弃，commit `67330ba`）→
Electrobun → Tauri v2（现在）。中途每一次都付出了迁移成本，所以这次必须先把"到底为什么要换"
写清楚，否则第五轮还会来。

真正让人下决心的是**发给别人的体验**，不是技术偏好：

1. **未签名被系统拦下这件事，Electrobun 让它更吓人。** Windows 上用户拿到的是
   `win-x64-…-Setup.zip`，解压出来才有一个 `Setup.exe`；一个被 SmartScreen 拦下的陌生 zip，
   比一个被拦下的 exe 更让人不敢双击。
2. **每个用户首次启动都要往自己目录里解出约 700MB。** 实测
   `~/Library/Application Support/dev.docanon.app/` = 687MB —— 那是 Electrobun 把未压缩的 tar
   留一份做更新/卸载底座。对"装完就想用"的用户，这是白白多出来的 700MB。
3. **工具链太小众。** Hutch 没有交叉打包、没有 `macos-x64` 产物、Windows 侧产物是 zip，
   社区里查不到别人的踩坑记录。Tauri 有官方 action、有 npm 分发的 CLI、有大量同构项目可参照。

同时必须先排除掉当年弃用 Tauri 的那个理由：**PDF 抖动**。用同一个 `file-viewer` 预览、
在 WebKit 内核里量了 8 秒（`tests/e2e/webkit/jitter-check.mjs`）：`dimsUnique:["466x559"]`、
`scrollUnique:[28]`、`resizes8s:1` —— 稳定。Electrobun 时期也没有复现过。也就是说那个抖动
不是这个内核的必然结果，它不构成换壳的障碍。

## 决定

换成 **Tauri v2**（Rust 壳），并把 Electrobun 时期攒下的每一条实测约束照搬过去。

## 为什么这样做

- 壳只做四件事：找资源根 → 起 Python 侧车 → 等 `/health` → 把窗口切过去。界面、引擎、产物全在
  Python 侧 —— 换壳不该动业务，这也是能换第三次的前提。
- 资源根、可写数据目录、侧车选择、父进程监视、pid 校验这些"踩出来"的逻辑逐条移植，
  不顺手"重写得更漂亮"：每一条的失败模式都是静默的（拿系统 python3 起后端、把模型写进只读目录、
  用别人的旧孤儿开窗），重写等于把踩过的坑再踩一遍。
- 顺手补了一条以前没有的：**窗口先开、再等后端**。等就绪才开窗，在首次使用时（要先加载本地引擎）
  就是双击后黑屏一分钟 —— 看起来完全像坏了。

## 代价与已知不足

- 改壳要装 Rust 工具链（`rustup`），比"改 JS 壳"门槛高一点。日常开发不需要它（壳只是窗口包装）。
- 打包比 Electrobun 慢：Rust release 编译几十秒，第一次要下依赖。
- **签名与公证的问题一点没解决**：macOS 首次仍要右键→「打开」，Windows 首次仍要「更多信息」→「仍要运行」。
  要改得买 Apple 开发者账号（$99/年），与壳无关。
- macOS 的 dmg 反而略大（240MB vs 214MB）：不再有自解包，但 Tauri 的 dmg 压缩率不如原来的 tar.zst。
  **下载略大、磁盘占用小得多** —— 这个取舍是有意的。

## 证据

- 包内布局（实测）：`doc-anonymizer.app/Contents/Resources/docanon/{configs,apps,samples,var,sidecar}`；
  资源复制保留可执行位（侧车进包仍是 `755`，否则"装上了后端起不来"）。
- 脱离仓库可用：把 `.app` 拷到 `/tmp` 连跑三次，`/health` 都正常应答（`{"ok":true,"pid":…,"version":"0.3.0"}`）。
- 版本号只有一处真相：`packages/docanon-core/pyproject.toml`，其余三处由 `tests/test_desktop.py` 钉住。
- 回滚路径：Electrobun 壳在 `git log` 的 `6ac8645` 之后（本次提交之前）可查；sidecar / 资源根 / 生命周期
  逻辑一行没动，所以回滚只需换回 `apps/desktop/` 与 `scripts/dev.sh dist` 的打包段。
