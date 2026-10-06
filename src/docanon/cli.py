"""docanon 命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .mapping import MappingStore
from .pipeline import prepare_detectors, process_file

SUPPORTED = {".txt", ".md", ".markdown", ".text", ".docx", ".pdf", ".xlsx", ".csv",
             ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

# 退出码: 0 全部处理, 1 输入有误, 2 有文件未产出脱敏结果
EXIT_OK, EXIT_INPUT, EXIT_PARTIAL = 0, 1, 2


def _collect(target: Path) -> tuple[list[Path], list[Path], Path]:
    """返回 (可处理文件, 不支持的文件, 相对路径基准目录)。"""
    if target.is_file():
        files, base = [target], target.parent
    else:
        base = target
        files = [
            p for p in sorted(target.rglob("*"))
            if p.is_file()
            and not any(part.startswith(".") for part in p.relative_to(target).parts)
        ]
    supported = [p for p in files if p.suffix.lower() in SUPPORTED]
    unsupported = [p for p in files if p.suffix.lower() not in SUPPORTED]
    return supported, unsupported, base


def _load_previous_manifest(path: Path) -> dict:
    """上一次 run 写下的清单; 读不出来就直接崩, 让调用处的 except 上报。"""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        # 引擎预检放在写任何文件之前: 少一层检测器的产物比没有产物更危险
        prepare_detectors(config)
    except Exception as exc:  # noqa: BLE001
        print(f"未开始处理: {exc}", file=sys.stderr)
        return EXIT_INPUT
    target = Path(args.input)
    if not target.exists():
        print(f"输入不存在: {target}", file=sys.stderr)
        return EXIT_INPUT
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    supported, unsupported, base = _collect(target)

    mapping_path = out_dir / "mapping.json"
    manifest_path = out_dir / "manifest.json"
    # 累加而不是覆盖: 同一个 -o 目录多次 run 时, 上一次的替换值与清单记录必须留着,
    # 否则先前产物的原文就丢了(还原失败), 而清单却不再描述目录里实际有什么。
    try:
        store = MappingStore.load(mapping_path) if mapping_path.exists() else MappingStore()
        previous = _load_previous_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print(
            f"输出目录里已有 {mapping_path.name}/{manifest_path.name} 但读不出来: {exc}\n"
            f"为了不覆盖上一次的记录, 本次未执行。请换一个空的 -o 目录。",
            file=sys.stderr,
        )
        return EXIT_INPUT

    by_source: dict[str, dict] = {}
    for entry in previous.get("files", []):
        if isinstance(entry, dict) and entry.get("source"):
            by_source[entry["source"]] = entry
    inputs = list(previous.get("inputs", []))
    if str(target) not in inputs:
        inputs.append(str(target))

    for path in supported:
        rel = path.relative_to(base)
        try:
            res = process_file(path, out_dir, config, store, rel=rel)
        except Exception as exc:  # noqa: BLE001
            print(f"[失败] {rel}: {exc}", file=sys.stderr)
            by_source[str(rel)] = {"source": str(rel), "status": "error", "error": str(exc)}
            continue
        print(f"[完成] {rel} -> {res.output_path}  {res.entity_counts}")
        by_source[str(rel)] = {
            "source": str(rel),
            "status": "ok",
            "outputs": res.outputs,
            "counts": res.entity_counts,
        }

    for path in unsupported:
        rel = path.relative_to(base)
        print(
            f"[不支持] {rel} ({path.suffix or '无扩展名'}) —— 未脱敏, 不要当成已处理",
            file=sys.stderr,
        )
        by_source[str(rel)] = {
            "source": str(rel),
            "status": "unsupported",
            "suffix": path.suffix,
        }

    entries = list(by_source.values())
    total: dict[str, int] = {}
    for entry in entries:
        for k, v in (entry.get("counts") or {}).items():
            total[k] = total.get(k, 0) + v
    summary = {
        "processed": sum(1 for e in entries if e["status"] == "ok"),
        "errors": sum(1 for e in entries if e["status"] == "error"),
        "unsupported": sum(1 for e in entries if e["status"] == "unsupported"),
    }

    store.save(mapping_path)
    manifest_path.write_text(
        json.dumps(
            {
                "inputs": inputs,
                "files": entries,
                "totals": total,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    skipped = summary["errors"] + summary["unsupported"]
    print(f"\n命中统计: {total or '无'}")
    print(f"清单: {manifest_path}")
    print(f"映射表(含原文, 切勿与脱敏文件一起外发): {mapping_path}")
    if skipped:
        print(
            f"⚠ 清单里累计 {skipped} 个文件没有脱敏产物, 详见 {manifest_path.name}",
            file=sys.stderr,
        )
        return EXIT_PARTIAL
    return EXIT_OK


def cmd_web(args: argparse.Namespace) -> int:
    from .server import serve

    serve(args.port, args.config, not args.no_browser)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    store = MappingStore.load(args.mapping)
    text = Path(args.input).read_text(encoding="utf-8")
    for repl, original in sorted(store._reverse.items(), key=lambda x: -len(x[0])):
        text = text.replace(repl, original)
    out = Path(args.out) if args.out else Path(args.input).with_suffix(".restored.txt")
    out.write_text(text, encoding="utf-8")
    print(f"已还原 -> {out}")
    return 0


def cmd_engines(args: argparse.Namespace) -> int:
    """列出这份配置下实际加载得起来的引擎(含不可用的原因)。"""
    from .engines import list_engines

    try:
        config = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"配置读不了: {exc}", file=sys.stderr)
        return EXIT_INPUT

    rows = list_engines(config)
    broken = [r for r in rows if r["status"].startswith(("加载失败", "不可用"))]
    for r in rows:
        caps = ", ".join(r["capabilities"]) or "-"
        print(f"{r['kind']:<4} {r['name']:<12} {r['status']:<30} {caps}")
    if broken:
        sys.stdout.flush()
        print(
            f"\n⚠ {len(broken)} 个已启用的引擎起不来, 用这份配置跑不出完整结果。",
            file=sys.stderr,
        )
        return EXIT_PARTIAL
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docanon", description="本地文档脱敏工具")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="处理文件或目录")
    run.add_argument("input", help="输入文件或目录")
    run.add_argument("-o", "--out", default="out", help="输出目录 (默认 out)")
    run.add_argument("-c", "--config", default=None, help="配置文件路径")
    run.set_defaults(func=cmd_run)

    restore = sub.add_parser("restore", help="按映射表还原脱敏文本")
    restore.add_argument("input", help="脱敏后的文件")
    restore.add_argument("--mapping", required=True, help="mapping.json 路径")
    restore.add_argument("-o", "--out", default=None, help="输出文件")
    restore.set_defaults(func=cmd_restore)

    engines = sub.add_parser("engines", help="列出这份配置下实际可用的引擎及其能力")
    engines.add_argument("-c", "--config", default=None)
    engines.set_defaults(func=cmd_engines)

    web = sub.add_parser("web", help="启动轻量 Web 界面")
    web.add_argument("-p", "--port", type=int, default=8000)
    web.add_argument("-c", "--config", default=None)
    web.add_argument("--no-browser", action="store_true")
    web.set_defaults(func=cmd_web)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
