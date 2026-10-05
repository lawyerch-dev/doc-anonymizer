/**
 * doc-anonymizer 桌面壳 (Electron 主进程)
 *
 * 职责单一: 拉起本地 Python 服务(docanon web) → 打开窗口加载它。
 * 开发时浏览器访问同一地址即可; 壳只是把它装进一个原生窗口。
 *
 * 可通过环境变量覆盖:
 *   DOCANON_PYTHON  Python 解释器路径 (默认 <root>/.venv/bin/python, 退回 python3)
 *   DOCANON_CONFIG  配置文件名 (默认 configs/onnx.yaml)
 *   DOCANON_PORT    服务端口 (默认 8770)
 */
const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const http = require('node:http');

const ROOT = path.resolve(__dirname, '..', '..');
const PORT = Number(process.env.DOCANON_PORT || 8770);
const CONFIG = process.env.DOCANON_CONFIG || 'configs/onnx.yaml';
const URL = `http://127.0.0.1:${PORT}`;
let child = null;

function resolvePython() {
  if (process.env.DOCANON_PYTHON) return process.env.DOCANON_PYTHON;
  const venv = path.join(ROOT, '.venv', 'bin', 'python');
  const fs = require('node:fs');
  return fs.existsSync(venv) ? venv : 'python3';
}

function startServer() {
  const py = resolvePython();
  child = spawn(py, ['-m', 'docanon.cli', 'web', '--no-browser', '-p', String(PORT), '-c', CONFIG], {
    cwd: ROOT,
    env: { ...process.env, PYTHONPATH: path.join(ROOT, 'src') },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (d) => process.stdout.write(`[server] ${d}`));
  child.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));
  child.on('exit', (code) => { if (code && code !== 0) console.error('Python 服务退出, code =', code); });
}

function waitForServer(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(`${URL}/health`, (res) => {
        res.resume();
        res.statusCode === 200 ? resolve() : retry();
      }).on('error', retry);
    };
    const retry = () => (Date.now() > deadline ? reject(new Error('服务启动超时')) : setTimeout(tick, 500));
    tick();
  });
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    title: '文档脱敏工具',
    backgroundColor: '#f5f6f8',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true },
  });
  // 外链用系统浏览器打开
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
  await win.loadURL(URL);
  if (process.env.DOCANON_DEV === '1') win.webContents.openDevTools();
}

app.whenReady().then(async () => {
  startServer();
  try {
    await waitForServer();
  } catch (e) {
    console.error(e.message);
  }
  await createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { if (child) { child.kill('SIGTERM'); child = null; } });
