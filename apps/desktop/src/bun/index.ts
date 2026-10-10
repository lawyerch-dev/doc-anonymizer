// Electrobun 主进程: 拉起本地 Python 服务(docanon web) → 打开窗口加载它(系统 WebView)。
import { ApplicationMenu, BrowserWindow } from "electrobun/main";
import { spawn } from "bun";
import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";

// 项目根: DOCANON_ROOT 优先, 否则从本文件逐级向上找带 `configs/default.yaml` 的目录。
// 不能用固定层数的 "..": dev 构建产物在 `<root>/apps/desktop/build/**.app` 里面, 层数随打包布局变,
// 猜错的后果是拿系统 python3(可能连 docanon 都没装)去起后端, 报一堆 ModuleNotFoundError。
//
// 打包态多认一种标记: `<dir>/docanon/configs/default.yaml` —— 那是随包发出去的资源根
// (见 scripts/dev.sh dist), 它自带 sidecar, 不需要 .venv 也不需要仓库。
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

/** 打包态的兜底: 壳自己就住在包的可执行文件目录里, 资源根在它附近的资源目录下。
 *  两个平台连大小写都不同(macOS 是 `Contents/Resources`, Windows 是 `resources`), 也都可能是
 *  资源目录下的 `app/`, 所以逐个试一遍 —— 试错的代价只是几次 stat。 */
function fromBundle(): Root | null {
	const exe = dirname(process.execPath);
	for (const near of [exe, dirname(exe)]) {
		for (const rel of ["Resources/app", "Resources", "resources/app", "resources"]) {
			const hit = rootAt(join(near, rel));
			if (hit) return hit;
		}
	}
	return null;
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

/** 用户数据目录(各平台习惯不同)。壳把模型与用户自建方案放这里。 */
function dataDir(): string {
	if (process.env.DOCANON_DATA) return process.env.DOCANON_DATA;
	if (process.platform === "win32") {
		return join(process.env.LOCALAPPDATA || join(homedir(), "AppData", "Local"), PACKAGED_DIR);
	}
	if (process.platform === "darwin") {
		return join(homedir(), "Library", "Application Support", PACKAGED_DIR);
	}
	return join(process.env.XDG_DATA_HOME || join(homedir(), ".local", "share"), PACKAGED_DIR);
}

// 可写状态(下载得到的模型、用户配置)不能落在资源根里: 打包后它在安装目录内部 ——
// 那里可能只读(macOS 的 App Translocation 会把包挂到只读的随机路径上), 卸载/升级还会连它一起清掉。
// 所以打包态一律落到用户数据目录, 并把路径通过 DOCANON_DATA 交给 Python 侧(见 resources.WRITABLE)。
const DATA = found.packaged || process.env.DOCANON_DATA ? dataDir() : "";
if (DATA) mkdirSync(DATA, { recursive: true });

const PORT = Number(process.env.DOCANON_PORT || 8770);
const CONFIG = process.env.DOCANON_CONFIG || "configs/onnx.yaml";
const URL = `http://127.0.0.1:${PORT}`;

// 打包态跑 sidecar 可执行文件(PyInstaller 产物, 自带解释器与依赖);
// 源码态跑 .venv 里的 python。两条路的参数完全一样 —— sidecar 的入口就是 docanon_core.cli:main。
// Windows 的产物带 `.exe`, 所以两个名字都试: 只认一个的话会静默退到系统 python3 上, 报一堆
// ModuleNotFoundError —— 那是"看着起来了、其实什么都没起来"的假故障。
function sidecar(): string | null {
	for (const name of ["docanon-server", "docanon-server.exe"]) {
		const p = join(ROOT, "sidecar", name);
		if (existsSync(p)) return p;
	}
	return null;
}

function backend(): string[] {
	if (process.env.DOCANON_PYTHON) {
		return [process.env.DOCANON_PYTHON, "-m", "docanon_core.cli", ...args()];
	}
	const exe = sidecar();
	if (exe) {
		return [exe, ...args()];
	}
	// Windows 的 venv 把可执行文件放在 Scripts/ 下, 名字也不一样
	const venv = join(ROOT, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
	if (existsSync(venv)) {
		return [venv, "-m", "docanon_core.cli", ...args()];
	}
	console.error(
		`[docanon] 既没有打包 sidecar(${ROOT}/sidecar)也没有 ${venv}, 退回 python3 —— ` +
			"它必须能 import docanon(没装就会启动失败)。建议设置 DOCANON_PYTHON。",
	);
	return ["python3", "-m", "docanon_core.cli", ...args()];
}

function args(): string[] {
	return ["web", "--no-browser", "-p", String(PORT), "-c", CONFIG];
}

console.log(
	`[docanon] 资源根=${ROOT}${DATA ? ` 数据目录=${DATA}` : ""} 运行方式=${sidecar() ? "侧车" : "源码"}`,
);

// 从 Finder 双击启动时 macOS 给的 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin —— 而 `llama-server`
// 与 `soffice` 都是用户自己装的(brew 装在 /opt/homebrew/bin), 不补上就会出现"终端里明明装了,
// 双击却说没有"。Windows 拿的是注册表里的用户+系统 PATH, 没这个问题, 也不用补。
// 分隔符必须用 path.delimiter: Windows 是 `;`, 硬写 ":" 会把整条 PATH 弄坏。
function backendPath(): string {
	const extra = process.platform === "darwin" ? ["/opt/homebrew/bin", "/usr/local/bin"] : [];
	return [process.env.PATH, ...extra].filter(Boolean).join(delimiter);
}

const cmd = backend();
const child = spawn({
	cmd,
	cwd: ROOT,
	// windowsHide: 侧车是控制台子系统的程序, 不压住的话 Windows 上会多弹一个黑框
	windowsHide: true,
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
	console.error(
		`[docanon] ${err} —— 直接跑 "${cmd.join(" ")}" 能看到具体原因`,
	);
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
