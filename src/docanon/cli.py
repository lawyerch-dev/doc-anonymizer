"""docanon 命令行入口。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .job import RedactionJob
from .mapping import MappingStore

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
    target = Path(args.input)
    if not target.exists():
        print(f"输入不存在: {target}", file=sys.stderr)
        return EXIT_INPUT
    try:
        config = load_config(args.config)
        job = RedactionJob(Path(args.out), config, resume=args.resume)
        # 引擎预检放在写任何文件之前: 少一层检测器的产物比没有产物更危险
        job.prepare()
    except Exception as exc:  # noqa: BLE001
        print(f"未开始处理: {exc}", file=sys.stderr)
        return EXIT_INPUT

    supported, unsupported, base = _collect(target)
    job.out_dir.mkdir(parents=True, exist_ok=True)
    job.note_input(target)

    if args.resume:
        if not job.covers_input(target):
            print("提示: 清单里没有这个输入, 按全量处理(续跑要用同一个 -o)。", file=sys.stderr)
        stale = job.pending_output_count()
        if stale:
            print(f"清单里 {stale} 条记录写着已处理但产物已不在, 本次重做。", file=sys.stderr)

    total = len(supported) + len(unsupported)
    print(f"待处理 {total} 个文件 -> {job.out_dir}")
    index = done = skipped = 0
    interrupted = False
    try:
        for path in supported:
            index += 1
            rel = path.relative_to(base)
            if job.is_done(str(rel)):
                skipped += 1
                print(f"[{index}/{total}] 跳过(已脱敏) {rel}", flush=True)
                continue
            entry = job.run_file(path, rel)
            job.record(str(rel), entry)
            if entry["status"] == "ok":
                done += 1
                print(f"[{index}/{total}] 完成 {rel}  {entry['counts'] or '无命中'}", flush=True)
            else:
                print(f"[{index}/{total}] 失败 {rel}: {entry['error']}", file=sys.stderr, flush=True)
        for path in unsupported:
            index += 1
            rel = path.relative_to(base)
            job.record(str(rel), {
                "source": str(rel), "status": "unsupported", "suffix": path.suffix,
            })
            print(
                f"[{index}/{total}] 不支持 {rel} ({path.suffix or '无扩展名'})"
                " —— 未脱敏, 不要当成已处理",
                file=sys.stderr, flush=True,
            )
    except KeyboardInterrupt:
        interrupted = True
        print(
            f"\n已中断: 本次做完 {done} 个、跳过 {skipped} 个。账本已落盘, 用 --resume 接着跑。",
            file=sys.stderr,
        )

    summary = job.tally()
    print(f"\n命中统计: {job.totals() or '无'}")
    if job.entries:
        print(f"清单: {job.manifest_path}")
        print(f"映射表(含原文, 切勿与脱敏文件一起外发): {job.mapping_path}")
    else:
        print("本次没有任何文件入账, 未写清单与映射表。")
    unfinished = summary["errors"] + summary["unsupported"]
    if not interrupted and unfinished:
        print(
            f"⚠ 清单里累计 {unfinished} 个文件没有脱敏产物, 详见 {job.manifest_path.name}",
            file=sys.stderr,
        )
    if interrupted or unfinished:
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
    run.add_argument(
        "-r", "--resume", action="store_true",
        help="跳过清单里已脱敏且产物仍在的文件(中断或失败后接着跑, 需同一个 -o)",
    )
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
