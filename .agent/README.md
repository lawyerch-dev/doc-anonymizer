# .agent/ — 给 agent（和人）看的分类规范

`AGENTS.md` 是**入口与索引**；细则按主题拆在这里，一个主题一个文件。这样做的原因很实在：
一条 160 行的大杂烩没人（也没有 agent）会读完再动手，而按主题拆开后，改前端就读前端那篇。

```
.agent/
├── README.md       ← 本文件：这套目录怎么用
└── rules/          ← 分类细则（现状权威）
    ├── 01-commands.md      命令、脚本、dev.sh 入口
    ├── 02-packages.md      Python 五包边界、引擎注册、可搬运性
    ├── 03-resources.md     资源根 / LAYOUT / 配置 / 部署契约 / 模型获取
    ├── 04-outputs.md       产物命名、账本纪律、退出码三态
    ├── 05-security.md      脱敏安全边界（PDF 栅格化、mapping.json、空串还原坑）
    ├── 06-testing.md       测试纪律与各守卫测试的分工
    ├── 07-frontend.md      前端两条契约、共享组件包、官网/文档站
    ├── 08-docs.md          文档怎么写、写在哪（一个主题一个出处）
    └── 09-environment.md   环境、可再生资产、samples、桌面壳约束
```

## 怎么用

- **动手前**：读 `AGENTS.md` 的"六条不可违反"，再按主题表读你将要改的那一篇。
- **写完**：改行为的同步 README；改边界的同步 `AGENTS.md` 与对应 rule。
- **加一篇 rule**：主题足够大（≥ 10 行、会被反复引用）才拆；在 `AGENTS.md` 的主题表加一行——
  `tests/test_docs.py` 会检查每个 rules 文件都被 `AGENTS.md` 引用到，没人认领的规则会红。

## 硬性维护约定（都有测试）

| 约定 | 谁盯 |
|---|---|
| `AGENTS.md` 保持短（≤ 80 行），细则放 rules | `tests/test_docs.py` |
| 每篇 rule ≤ 60 行，超了就该再拆 | `tests/test_docs.py` |
| 每个 rules 文件都被 `AGENTS.md` 索引到 | `tests/test_docs.py` |
| rules 里的路径与链接必须真实存在 | `tests/test_docs.py` |

> 面向用户的说明文档在 `README.md` 与 `docs/`；这里是**面向开发者的操作契约**，两者不混。
