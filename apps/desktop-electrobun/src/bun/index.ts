// Electrobun 主进程: 拉起本地 Python 服务(docanon web) → 打开窗口加载它(系统 WebView)。
import { BrowserWindow } from "electrobun/main";
import { spawn } from "bun";
import { existsSync } from "node:fs";
import { join } from "node:path";

// 项目根: 优先用环境变量(打包后路径会变), 退回源码树推断。
const ROOT = process.env.DOCANON_ROOT || join(import.meta.dir, "..", "..", "..", "..");
const PORT = Number(process.env.DOCANON_PORT || 8771);
const CONFIG = process.env.DOCANON_CONFIG || "configs/onnx.yaml";
const URL = `http://127.0.0.1:${PORT}`;

function python(): string {
	if (process.env.DOCANON_PYTHON) return process.env.DOCANON_PYTHON;
	const venv = join(ROOT, ".venv", "bin", "python");
	if (existsSync(venv)) return venv;
	console.error(`[docanon] 未找到 .venv 的 Python(${venv})，请设置 DOCANON_PYTHON 或 DOCANON_ROOT`);
	return "python3";
}

// 拉起 Python 后端(sidecar)
const child = spawn({
	cmd: [python(), "-m", "docanon.cli", "web", "--no-browser", "-p", String(PORT), "-c", CONFIG],
	cwd: ROOT,
	env: { ...process.env, PYTHONPATH: join(ROOT, "src") },
	stdout: "inherit",
	stderr: "inherit",
});

async function waitForServer(timeoutMs = 60000): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		try {
			const res = await fetch(`${URL}/health`);
			if (res.ok) return;
		} catch {}
		await Bun.sleep(500);
	}
	throw new Error("Python 服务启动超时");
}

await waitForServer();

const mainWindow = new BrowserWindow({
	title: "文档脱敏工具",
	url: URL,
	frame: { width: 1280, height: 860, x: 200, y: 120 },
});

process.on("exit", () => child.kill());
console.log("doc-anonymizer (electrobun) 已启动:", URL);
