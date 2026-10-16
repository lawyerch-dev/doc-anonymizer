# Agent Note: 把 Block.locator / ExtractedDoc.meta 从无类型 dict 收成有名字的键

Status: proposed
Date: 2026-10-16
Class: architecture

## 问题

`docanon_contract.contract` 里 `Block.locator` 与 `ExtractedDoc.meta` 都是
`dict[str, Any]`，键名只在"写"和"读"两边靠约定对齐：

- 抽取器往 `meta`/`locator` 塞键（PDF 的 `_scanned_images`、旧格式的 `_convert_workdir`、
  以及 `format`/`out_ext`/`converted_from` 等）；core 的 `redaction/writers.py` 再按
  `line`/`paragraph`/`row`/`col`/`cell`/`sheet`/`page`/`bbox` 的 `if/elif` 猜着读。
- 键名没有共同出处。引擎重命名一个 meta 键，core 会**静默失效** —— 而 `tests/test_architecture.py`
  用 AST 锁的是 import 方向，锁不住数据契约，这类漂移它抓不到。

## 为什么现在不做

这是**跨包契约变更**：要改 `docanon-contract` 的数据类型，牵动三个引擎包与 core 的读写两侧，
是本次体检里设计面最大的一个。按全仓梳理报告（`docs/specs/2026-10-16-codebase-audit.md`）的建议顺序，
它排在最后，且应走 grill → spec → tickets → TDD，而不是顺手改。破坏契约的风险（静默失效比 import
越界更隐蔽）不值得在收尾批次里冒。

## 方向（留作后续设计的起点，不是定稿）

1. 先在契约里给 `locator`/`meta` 的键起**名字**（模块级常量或 `StrEnum`），作为唯一出处；
   引擎与 core 都引用它 —— 这一步不改结构、可增量。
2. 再按定位种类（文件行 / 段落 / 单元格 / 页面 / 图 bbox）把 `locator` 收成几个显式的 dataclass
   或一个带 `kind` 判别字段的联合，让 `writers` 的 `if/elif` 退化成一次分派。
3. 加一条守卫：引擎写进 `meta` 的键必须在契约登记过（AST 或运行时白名单），把"没有名字的键"
   挡在门外。
