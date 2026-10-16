# Agent Note: locator/meta 的键名收进 docanon_contract.keys

Status: implemented
Date: 2026-10-16
Class: architecture

## 问题

`Block.locator` 与 `ExtractedDoc.meta` 是 `dict[str, Any]`，键名此前只在写入方（抽取器）与
读取方（core 的 `redaction/writers.py`、`pipeline.py`）各自靠约定对齐：PDF 的 `_scanned_images`、
旧格式的 `_convert_workdir` `converted_from` `out_ext`、OCR 的 `format` `needs_image_redaction`，
以及 locator 的 `line` `paragraph` `page` `bbox` `row` `col` `sheet` `cell` `score`。

引擎或抽取器改一个键名，core 会**静默失效** —— 交出一份"少了回写"的产物 —— 而
`tests/test_architecture.py` 用 AST 锁的是 import 方向，锁不住数据契约。

## 决定

键名收进 `docanon_contract.keys`（标准库模块，随契约一起可整块搬走），写入方与读取方都引用它。
新增 `tests/test_contract_keys.py` 钉住"抽取/回写层不许再写裸键名" —— 只查**够独特**的 meta 键
（`_scanned_images` / `_convert_workdir` / `needs_image_redaction` / `scanned_pages` /
`converted_from` / `out_ext`），`line` / `format` / `row` 这类泛用词不进守卫，免得误伤普通字符串
（它们仍走 `keys.*`，只是不做字面量守卫）。

改名现在只动一处，不一致会变成 ImportError / NameError，而不是悄悄少读一份数据。

## 代价

键名多了一层间接（`keys.LINE` 而非 `"line"`），读代码时要去 `keys.py` 才知道实际字符串。换来的
是唯一出处 + 一条守卫。

**没做**（留作后续）：把 `locator` 按定位种类收成 dataclass 或带判别字段的联合，让 `writers` 的
`if/elif` 退化成一次分派。那是更大的结构变更；在字典存储不变的前提下，"静默失效"这条风险已经消除。
