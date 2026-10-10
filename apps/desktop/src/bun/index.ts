// Electrobun 主进程: 拉起本地 Python 服务(docanon web) → 打开窗口加载它(系统 WebView)。
import { ApplicationMenu, BrowserWindow } from "electrobun/main";
import { spawn } from "bun";
import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";

// 项目根: DOCANON_ROOT 优先, 否则从本文件逐级向上找带 `configs/default.yaml` 的目录。
// 不能用固定层数的 "..": dev 构建产物在 `<root>/apps/desktop/build/**.app` 里面, 层数随打包布局变,
// 猜错的后果是拿系统 python3(可能连 docanon 都没装)去起后端, 报一堆 ModuleNotFoundError。
//
// 打包态多认一种标记: `<dir>/docanon/configs/default.yaml` —— 那是随包发出去的资源根
// (见 scripts/build_desktop.sh), 它自带 sidecar, 不需要 .venv 也不需要仓库。
const DEV_MARKER = join("configs", "default.yaml");
const PACKAGED_MARKER = join("docanon", "configs", "default.yaml");
const PACKAGED_DIR = "docanon";

type Root = { root: string; packaged: boolean };

function rootAt(dir: string): Root | null {
	if (existsSync(join(dir, PACKAGED_MARKER))) return { root: join(dir, PACKAGED_DIR), packaged: true };
	if (existsSync(join(dir, DEV_MARKER))) return { root: dir, packaged: false };
	return null;
}

function findRoot(start: string): Root | null {
	let dir = resolve(start);
	for (;;) {
		const hit = rootAt(dir);
		if (hit) return hit;
		const parent = dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
}

/** 打包态的兜底: 壳自己就住在 `<bundle>/Contents/MacOS/launcher`, 资源根在它隔壁的 Resources 下。 */
function fromBundle(): Root | null {
	const resources = join(dirname(process.execPath), "..", "Resources");
	// Electrobun 把 `copy` 里的东西放在 Resources/app 下, 先按这个来, 再退一步看 Resources 本身
	return rootAt(join(resources, "app")) ?? rootAt(resources);
}

const found = process.env.DOCANON_ROOT
	? { root: resolve(process.env.DOCANON_ROOT), packaged: existsSync(join(process.env.DOCANON_ROOT, PACKAGED_DIR)) }
	: (findRoot(import.meta.dir) ?? fromBundle());
if (!found) {
	console.error(
		`[docanon] 找不到资源根(向上查找 ${DEV_MARKER} 与 ${PACKAGED_MARKER} 都没有)。` +
			"源码树里跑请确认 configs/default.yaml 还在; 打包运行时请设置 DOCANON_ROOT 指向资源根。",
	);
	process.exit(1);
}
const ROOT = found.root;

// 可写状态(下载得到的模型、用户配置)不能落在资源根里: 打包后它在 .app 内部,
// 首次运行还可能被 App Translocation 挂到只读的随机路径上。统一落到用户数据目录。
const DATA = process.env.DOCANON_DATA || (found.packaged ? join(homedir(), "Library", "Application Support", PACKAGED_DIR) : "");
if (DATA) mkdirSync(DATA, { recursive: true });

const PORT = Number(process.env.DOCANON_PORT || 8770);
const CONFIG = process.env.DOCANON_CONFIG || "configs/onnx.yaml";
const URL = `http://127.0.0.1:${PORT}`;

// 打包态跑 sidecar 可执行文件(PyInstaller 产物, 自带解释器与依赖);
// 源码态跑 .venv 里的 python。两条路的参数完全一样 —— sidecar 的入口就是 docanon_core.cli:main。
const SIDECAR = join(ROOT, "sidecar", "docanon-server");

function backend(): string[] {
	if (process.env.DOCANON_PYTHON) {
		return [process.env.DOCANON_PYTHON, "-m", "docanon_core.cli", ...args()];
	}
	if (existsSync(SIDECAR)) {
		return [SIDECAR, ...args()];
	}
	const venv = join(ROOT, ".venv", "bin", "python");
	if (existsSync(venv)) {
		return [venv, "-m", "docanon_core.cli", ...args()];
	}
	console.error(
		`[docanon] 既没有打包 sidecar(${SIDECAR})也没有 ${venv}, 退回 python3 —— ` +
			"它必须能 import docanon(没装就会启动失败)。建议设置 DOCANON_PYTHON。",
	);
	return ["python3", "-m", "docanon_core.cli", ...args()];
}

function args(): string[] {
	return ["web", "--no-browser", "-p", String(PORT), "-c", CONFIG];
}

console.log(
	`[docanon] 资源根=${ROOT}${DATA ? ` 数据目录=${DATA}` : ""} 运行方式=${existsSync(SIDECAR) ? "侧车" : "源码"}`,
);

// 拉起 Python 后端(sidecar)。DOCANON_EXIT_WITH_PARENT: 壳被强杀时 JS 没机会收尸,
// 让后端自己盯着父进程(见 docanon/server.py 的 _watch_parent)。
// 从 Finder 双击启动时 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin —— `llama-server`(brew 装的)与
// `soffice` 都在 /opt/homebrew/bin, 不补上这两条就会出现"终端里明明装了, 双击却说没有"。
// 只加在**后端**的环境里, 不动壳自己的 PATH。
function backendPath(): string {
	return [process.env.PATH, "/opt/homebrew/bin", "/usr/local/bin"].filter(Boolean).join(":");
}

const cmd = backend();
const child = spawn({
	cmd,
	cwd: ROOT,
	// 源码态下五个包由 requirements-dev.txt 装进 .venv(editable), 不需要再拼 PYTHONPATH
	env: {
		...process.env,
		PATH: backendPath(),
		DOCANON_ROOT: ROOT,
		...(DATA ? { DOCANON_DATA: DATA } : {}),
		DOCANON_EXIT_WITH_PARENT: "1",
	},
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
