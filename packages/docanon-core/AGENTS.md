# AGENTS.md — docanon-core

app 本体：抽取 → 检测 → 脱敏回写 + 账本 + CLI + Web。目录分层
`extractors/` → `detectors/` → `redaction/`，外加 `pipeline.py`/`job.py`/`server/`。

- 只许用三个引擎包的**公开面**（`from docanon_engine_x import Y`），不许伸手进内部模块。
- **布局只有一处真相**：`src/docanon_core/resources.py` 的 `LAYOUT`。
- **一个 `-o` 就是唯一真相**：`manifest.json`/`mapping.json` 按源文件累加，别开平行目录。
- 测试：`packages/docanon-core/tests/`（布局/资源根/产物命名/账本/PDF/还原/服务生命周期）。

细则 → [`02-packages.md`](../../.agent/rules/02-packages.md)、[`03-resources.md`](../../.agent/rules/03-resources.md)、[`04-outputs.md`](../../.agent/rules/04-outputs.md)
