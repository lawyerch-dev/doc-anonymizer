import type { ElectrobunConfig } from "electrobun";

export default {
	app: {
		name: "doc-anonymizer",
		identifier: "dev.docanon.app",
		version: "0.1.0",
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
		},
		// 壳的一切构建产物都收在 build/ 下(已被 .gitignore 忽略), 免得仓库根多出 artifacts/
		artifactFolder: "build/artifacts",
		mac: { bundleCEF: false },
		linux: { bundleCEF: false },
		win: { bundleCEF: false },
	},
} satisfies ElectrobunConfig;
