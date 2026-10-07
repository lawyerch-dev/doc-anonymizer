# Agent Note: `restore` 的 remove 空串：还原动作反而把原文撒满全篇

Status: implemented

## 问题

`remove` 策略的替换值是**空串**。它进了反向表后，还原走 `str.replace("", …)` ——
空串能匹配每个字符的缝隙，于是原文被插到**每个字符之间**，一篇文档当场变成乱码。

## 决策

- 空串只进**正向**表（原文 → 空），绝不进 `MappingStore._reverse`；
- 还原走 `restorable_items()`（过滤空键），并对"有几条还原不了"给出提示；
- 即：`remove` 删掉的原文**无法还原** —— 这是设计后果，不是待修的 bug。

## 证据

`packages/docanon-core/tests/test_restore.py` 锁死这条（含"还原结果里不能出现缝隙插入"的断言）。
CLI 实跑会提示：`映射表里 N 条原文是 remove 策略删掉的(替换值为空串), 无法定位还原`。

## 教训

"空值"在双向映射里是危险哨兵：默认它会被当成合法键使用。凡是双向表，
先问一句"这个值放进去，反向查会怎样"。
