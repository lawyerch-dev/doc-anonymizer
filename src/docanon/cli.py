"""docanon 命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .mapping import MappingStore
from .pipeline import process_file

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


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    target = Path(args.input)
    if not target.exists():
        print(f"输入不存在: {target}", file=sys.stderr)
        return EXIT_INPUT
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    supported, unsupported, base = _collect(target)

    store = MappingStore()
    total: dict[str, int] = {}
    entries: list[dict] = []

    for path in supported:
        rel = path.relative_to(base)
        try:
            res = process_file(path, out_dir, config, store, rel=rel)
        except Exception as exc:  # noqa: BLE001
            print(f"[失败] {rel}: {exc}", file=sys.stderr)
            entries.append({"source": str(rel), "status": "error", "error": str(exc)})
            continue
        for k, v in res.entity_counts.items():
            total[k] = total.get(k, 0) + v
        print(f"[完成] {rel} -> {res.output_path}  {res.entity_counts}")
        entries.append(
            {"source": str(rel), "status": "ok", "outputs": res.outputs,
             "counts": res.entity_counts}
        )

    for path in unsupported:
        rel = path.relative_to(base)
        print(
            f"[不支持] {rel} ({path.suffix or '无扩展名'}) —— 未脱敏, 不要当成已处理",
            file=sys.stderr,
        )
        entries.append(
            {"source": str(rel), "status": "unsupported", "suffix": path.suffix}
        )

    mapping_path = out_dir / "mapping.json"
    store.save(mapping_path)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "input": str(target),
                "files": entries,
                "totals": total,
                "summary": {
                    "processed": sum(1 for e in entries if e["status"] == "ok"),
                    "errors": sum(1 for e in entries if e["status"] == "error"),
                    "unsupported": sum(1 for e in entries if e["status"] == "unsupported"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    skipped = len(unsupported) + sum(1 for e in entries if e["status"] == "error")
    print(f"\n命中统计: {total or '无'}")
    print(f"清单: {manifest_path}")
    print(f"映射表(含原文, 切勿与脱敏文件一起外发): {mapping_path}")
    if skipped:
        print(
            f"⚠ {skipped} 个文件没有脱敏产物, 详见 {manifest_path.name}",
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
