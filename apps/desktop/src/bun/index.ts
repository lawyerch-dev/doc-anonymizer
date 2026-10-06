// Electrobun 主进程: 拉起本地 Python 服务(docanon web) → 打开窗口加载它(系统 WebView)。
import { ApplicationMenu, BrowserWindow } from "electrobun/main";
import { spawn } from "bun";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

// 项目根: DOCANON_ROOT 优先, 否则从本文件逐级向上找带 `configs/default.yaml` 的目录。
// 不能用固定层数的 "..": dev 构建产物在 `<root>/apps/desktop/build/**.app` 里面, 层数随打包布局变,
// 猜错的后果是拿系统 python3(可能连 docanon 都没装)去起后端, 报一堆 ModuleNotFoundError。
const MARKER = join("configs", "default.yaml");

function findRoot(start: string): string | null {
	let dir = start;
	for (;;) {
		if (existsSync(join(dir, MARKER))) return dir;
		const parent = dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
}

const ROOT = process.env.DOCANON_ROOT || findRoot(import.meta.dir);
if (!ROOT) {
	console.error(
		`[docanon] 找不到项目根(向上查找 ${MARKER} 未命中)。` +
			"源码树里跑请确认 configs/default.yaml 还在; 打包运行时请设置 DOCANON_ROOT 指向资源根。",
	);
	process.exit(1);
}
const PORT = Number(process.env.DOCANON_PORT || 8770);
const CONFIG = process.env.DOCANON_CONFIG || "configs/onnx.yaml";
const URL = `http://127.0.0.1:${PORT}`;

function python(): string {
	if (process.env.DOCANON_PYTHON) return process.env.DOCANON_PYTHON;
	const venv = join(ROOT, ".venv", "bin", "python");
	if (existsSync(venv)) return venv;
	console.error(
		`[docanon] 未找到 ${venv}, 退回 python3 —— 它必须能 import docanon(没装就会启动失败)。` +
			"建议设置 DOCANON_PYTHON, 或先在仓库根建好 .venv。",
	);
	return "python3";
}

// 拉起 Python 后端(sidecar)。DOCANON_EXIT_WITH_PARENT: 壳被强杀时 JS 没机会收尸,
// 让后端自己盯着父进程(见 docanon/server.py 的 _watch_parent)。
const child = spawn({
	cmd: [python(), "-m", "docanon.cli", "web", "--no-browser", "-p", String(PORT), "-c", CONFIG],
	cwd: ROOT,
	env: { ...process.env, PYTHONPATH: join(ROOT, "src"), DOCANON_EXIT_WITH_PARENT: "1" },
	stdout: "inherit",
	stderr: "inherit",
});

async function waitForServer(timeoutMs = 60000): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		// 自己的后端死了就别再等: 端口上可能还答着话的是别人(旧孤儿), 等下去只会开出一个假窗口
		if (child.exitCode !== null) {
			throw new Error(`Python 后端已退出(code=${child.exitCode}); 端口 ${PORT} 多半被别的进程占着`);
		}
		let info: { pid?: number } | null = null;
		try {
			const res = await fetch(`${URL}/health`);
			if (res.ok) info = (await res.json()) as { pid?: number };
		} catch {
			info = null; // 还没起来
		}
		if (info) {
			if (info.pid && info.pid !== child.pid) {
				throw new Error(
					`端口 ${PORT} 上跑着另一个 docanon(pid=${info.pid}), 本壳的后端是 pid=${child.pid}。` +
						"先关掉它, 或用 DOCANON_PORT 换一个端口",
				);
			}
			return;
		}
		await Bun.sleep(500);
	}
	throw new Error("Python 服务启动超时");
}

// 后端起不来(模型缺失、端口被占、配置读不到)时要说清楚再退出, 不能留一个空窗口干等
try {
	await waitForServer();
} catch (err) {
	console.error(`[docanon] ${err} —— 直接跑 .venv/bin/docanon web -c ${CONFIG} 能看到具体原因`);
	child.kill();
	process.exit(1);
}

const mainWindow = new BrowserWindow({
	title: "文档脱敏工具",
	url: URL,
	frame: { width: 1280, height: 860, x: 200, y: 120 },
});

// 关窗即退出(单窗口工具) —— 关闭时回收 Python sidecar
mainWindow.on("close", () => {
	child.kill();
	process.exit(0);
});

// JS 能看见的退出路径都收一次尸。注意: Electrobun 自己的 SIGTERM quit 序列不会走到这里
// (实测过, 这几条救不了强杀), 所以真正的兜底是后端的 DOCANON_EXIT_WITH_PARENT 父进程监视。
function shutdown(): void {
	child.kill();
	process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.on("SIGHUP", shutdown);

// Electrobun 无默认应用菜单; ⌘Q 需自己绑。用显式 action 保证可控(而非依赖 role)。
ApplicationMenu.setApplicationMenu([
	{
		label: "文档脱敏工具",
		submenu: [
			{ role: "about" },
			{ type: "separator" },
			{ role: "hide" },
			{ role: "hideOthers" },
			{ role: "unhide" },
			{ type: "separator" },
			{ label: "退出 文档脱敏工具", action: "quit-app", accelerator: "q" }, // ⌘Q
		],
	},
	{
		label: "编辑",
		submenu: [
			{ role: "undo" },
			{ role: "redo" },
			{ type: "separator" },
			{ role: "cut" },
			{ role: "copy" },
			{ role: "paste" },
			{ role: "selectAll" },
		],
	},
	{
		label: "窗口",
		submenu: [
			{ role: "minimize" },
			{ role: "zoom" },
			{ type: "separator" },
			{ role: "close" }, // ⌘W
		],
	},
]);

// 处理自定义菜单动作(退出)
ApplicationMenu.on("application-menu-clicked", (event: unknown) => {
	console.log("[menu] event:", JSON.stringify(event));
	const action = (event as any)?.data?.action ?? (event as any)?.action;
	if (action === "quit-app") {
		child.kill();
		process.exit(0);
	}
});

process.on("exit", () => child.kill());
console.log("doc-anonymizer (electrobun) 已启动:", URL);
