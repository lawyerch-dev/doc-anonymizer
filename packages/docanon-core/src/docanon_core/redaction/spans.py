"""span 级文字改写: 脱敏回写(原文→替换值)与还原回填(替换值→原文)共用的两件小事。

- `apply_spans`: 在整段文字上按偏移从后往前替换(偏移彼此不重叠)。
- `rewrite_runs`: 把"整段坐标系"里的 span 映射回每个 run 的局部区间改写文字。

为什么必须共用一处: 偏移错位会**同时**造成漏脱敏与文件损坏, 是全项目风险最高的代码。
`writers`(脱敏)与 `restorers`(还原)是同一套偏移算法的正/逆运算, 不许各写一遍再靠注释对齐。
"""
from __future__ import annotations


def apply_spans(text: str, replacements: list[tuple[int, int, str]]) -> str:
    """replacements: [(start, end, replacement)], 按位置从后往前替换。"""
    for start, end, repl in sorted(replacements, key=lambda x: x[0], reverse=True):
        text = text[:start] + repl + text[end:]
    return text


def rewrite_runs(runs, repls: list[tuple[int, int, str]]) -> int:
    """把 (start, end, 替换文本) 这些 span 写回 `runs`, 返回实际替换的处数。

    替换值落在**起点所在的那个 run** 上, 后续被覆盖到的 run 只清掉重叠部分 —— 它们的字体
    属于被替换掉的那段文字, 留着会串味。起点 run 的属性(字体/字号/颜色)完整保留, 那是还原
    出来的原文 / 替换值该继承的样式。`runs` 是 docx 的 run 对象(只需有 `.text` 可读写)。
    """
    ranges: list[tuple[int, int]] = []
    pos = 0
    for run in runs:
        ranges.append((pos, pos + len(run.text)))
        pos += len(run.text)
    ordered = sorted(repls)
    done = 0
    for i, (a, b) in enumerate(ranges):
        rt = runs[i].text
        out: list[str] = []
        cursor = 0
        for s, e, rep in ordered:
            if e <= a or s >= b:
                continue
            ls = max(s, a) - a
            le = min(e, b) - a
            if ls > cursor:
                out.append(rt[cursor:ls])
            if a <= s < b:  # 替换文本落在本 run 起点
                out.append(rep)
                done += 1
            cursor = max(cursor, le)
        out.append(rt[cursor:])
        new = "".join(out)
        if new != rt:
            runs[i].text = new
    return done
