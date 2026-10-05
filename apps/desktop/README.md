# apps/desktop — 桌面壳 (Electron)

把本地 Python 服务 + Web UI 装进一个原生窗口。**开发时不用它**，直接 `docanon web` 用浏览器即可。

## 运行

```bash
# 1) 根目录准备好 Python 环境与依赖(见根 README)
# 2) 安装 electron
cd apps/desktop && npm install
# 3) 启动
npm start
```

壳会：用项目 `.venv` 的 Python 拉起 `docanon web`（默认 `configs/onnx.yaml`、端口 8770），
等 `/health` 就绪后打开窗口加载 `http://127.0.0.1:8770`。

## 可覆盖的环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DOCANON_PYTHON` | `<root>/.venv/bin/python`（退回 `python3`） | Python 解释器 |
| `DOCANON_CONFIG` | `configs/onnx.yaml` | 配置文件 |
| `DOCANON_PORT` | `8770` | 服务端口 |
| `DOCANON_DEV` | 空 | `1` 时自动开 DevTools |

## 打包(后续)

用 `electron-builder` 打成 `.dmg/.exe`，并把 Python 后端用 PyInstaller 打成单文件作为 sidecar 一起分发。
