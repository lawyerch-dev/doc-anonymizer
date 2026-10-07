# AGENTS.md — docanon-contract

**本包是引擎与 app 之间唯一的共享层**：`Block`/`Span`/`Detection` + `Engine` ABC。

- **只准 import 标准库**；`dependencies = []`（被 `tests/test_architecture.py` 锁死）。
- 改这里的类型 = 改两边（三个引擎 + core）的契约：改完必须全量测试。
- 测试：`packages/docanon-contract/tests/test_contract.py`。

细则 → [`02-packages.md`](../../.agent/rules/02-packages.md)
