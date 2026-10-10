import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { ElectrobunConfig } from "electrobun";

// 版本号只有一处真相: packages/docanon-core 的 pyproject(界面的版本号也从那儿读, 见/health)。
// 壳这边写死会得到"访达显示 0.1.0、界面写着 v0.2.0"这种东西, 所以构建时读一次。
function productVersion(): string {
	const pyproject = join(import.meta.dir, "..", "..", "packages", "docanon-core", "pyproject.toml");
	const found = /^version = "([^"]+)"/m.exec(readFileSync(pyproject, "utf-8"));
	if (!found) throw new Error(`读不出产品版本号: ${pyproject}`);
	return found[1];
}

// 可分发版要的资源根(见 scripts/build_desktop.sh): 一份 mirrored 仓库布局的树, 含
// configs / apps/web/dist / samples / var/vendor/file-viewer / sidecar(PyInstaller 产物)。
// Electrobun 的 `copy` 只能取**本项目内**的路径, 所以构建脚本先把它摆到 stage/docanon。
//
// 没有它照样能构建 —— 那是 dev 形态(壳从源码树向上找资源根)。但只要不是从源码树跑,
// 缺了它就是"双击打不开", 所以发布构建一律走 scripts/build_desktop.sh, 不要直接 npm run build。
const STAGED_ROOT = "stage/docanon";

export default {
	app: {
		name: "doc-anonymizer",
		identifier: "dev.docanon.app",
		version: productVersion(),
	},
	build: {
		mainProcess: "cottontail",
		cottontail: {
			entrypoint: "src/bun/index.ts",
		},
		views: {
			mainview: {
				entrypoint: "src/mainview/index.ts",
			},
		},
		copy: {
			"src/mainview/index.html": "views/mainview/index.html",
			...(existsSync(join(import.meta.dir, STAGED_ROOT)) ? { [STAGED_ROOT]: "docanon" } : {}),
		},
		// 壳的一切构建产物都收在 build/ 下(已被 .gitignore 忽略), 免得仓库根多出 artifacts/
		artifactFolder: "build/artifacts",
		mac: { bundleCEF: false },
		linux: { bundleCEF: false },
		win: { bundleCEF: false },
	},
} satisfies ElectrobunConfig;
