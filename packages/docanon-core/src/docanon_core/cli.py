"""docanon 命令行入口。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import convert
from .config import load_config
from .job import RedactionJob
from .redaction.mapping import MappingStore

SUPPORTED = {".txt", ".md", ".markdown", ".text", ".docx", ".pdf", ".xlsx", ".csv",
             ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

# 退出码: 0 全部处理, 1 输入有误, 2 有文件未产出脱敏结果
EXIT_OK, EXIT_INPUT, EXIT_PARTIAL = 0, 1, 2


def _collect(target: Path, config) -> tuple[list[Path], list[Path], Path]:
    """返回 (可处理文件, 不支持的文件, 相对路径基准目录)。

    旧格式(.doc/.xls/.wps)是否算"可处理"取决于 `config.legacy_convert`:
    关掉就回到旧行为, 一律进"不支持"桶。
    """
    if target.is_file():
        files, base = [target], target.parent
    else:
        base = target
        files = [
            p for p in sorted(target.rglob("*"))
            if p.is_file()
            and not any(part.startswith(".") for part in p.relative_to(target).parts)
        ]
    supported_ext = SUPPORTED | (set(convert.LEGACY_EXTENSIONS) if config.legacy_convert else set())
    supported = [p for p in files if p.suffix.lower() in supported_ext]
    unsupported = [p for p in files if p.suffix.lower() not in supported_ext]
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

    supported, unsupported, base = _collect(target, config)
    job.out_dir.mkdir(parents=True, exist_ok=True)
    job.note_input(target)

    # 旧格式要先转: 缺 LibreOffice 时整批记 unsupported(带原因), 而不是让它炸成 error
    legacy_blocked = None
    if any(p.suffix.lower() in convert.LEGACY_EXTENSIONS for p in supported):
        legacy_blocked = convert.unavailable_reason()

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
            if legacy_blocked and path.suffix.lower() in convert.LEGACY_EXTENSIONS:
                job.record(str(rel), {
                    "source": str(rel), "status": "unsupported",
                    "suffix": path.suffix, "reason": legacy_blocked,
                })
                print(
                    f"[{index}/{total}] 跳过(缺 LibreOffice) {rel}: {legacy_blocked}",
                    file=sys.stderr, flush=True,
                )
                continue
            entry = job.run_file(path, rel)
            job.record(str(rel), entry)
            if entry["status"] == "ok":
                done += 1
                if entry.get("converted"):
                    print(
                        f"[{index}/{total}] 完成 {rel}  已由 {entry['source_suffix']} 转换, 版式可能被重排",
                        flush=True,
                    )
                else:
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
    """按映射表还原**文本**产物。

    docx/xlsx/pdf/图片的产物是原格式回写(替换 run/单元格, 或涂黑), 没有可按映射表替换的纯文本,
    所以只接受 UTF-8 文本; 二进制进来时给明确原因, 而不是抛 UnicodeDecodeError 的栈。
    """
    try:
        store = MappingStore.load(args.mapping)
    except (OSError, ValueError) as exc:
        print(f"还原失败: 读不了映射表 {args.mapping}: {exc}", file=sys.stderr)
        return EXIT_INPUT

    src = Path(args.input)
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(
            f"还原失败: {src} 不是 UTF-8 文本。restore 只支持文本产物(txt/md/csv);"
            " docx/xlsx/pdf/图片产物是原格式回写, 没有可替换的纯文本。",
            file=sys.stderr,
        )
        return EXIT_INPUT
    except OSError as exc:
        print(f"还原失败: 读不了 {src}: {exc}", file=sys.stderr)
        return EXIT_INPUT

    for repl, original in store.restorable_items():
        text = text.replace(repl, original)
    out = Path(args.out) if args.out else src.with_suffix(".restored.txt")
    out.write_text(text, encoding="utf-8")
    print(f"已还原 -> {out}")
    skipped = store.unrestorable_count()
    if skipped:
        print(
            f"提示: 映射表里 {skipped} 条原文是 remove 策略删掉的(替换值为空串), 无法定位还原 ——"
            " 它们不会出现在还原结果里。",
            file=sys.stderr,
        )
    return 0


def cmd_engines(args: argparse.Namespace) -> int:
    """列出这份配置下实际加载得起来的引擎(含不可用的原因)。"""
    from .inventory import list_engines

    try:
        config = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"配置读不了: {exc}", file=sys.stderr)
        return EXIT_INPUT

    rows = list_engines(config)
    # 门禁只看**检测器**: 抽取器缺席(如旧格式缺 LibreOffice)是可选能力缺失,
    # 如实报告即可, 不该把整份引擎清单判成失败。
    broken = [r for r in rows
              if r["kind"] == "检测器" and r["status"].startswith(("加载失败", "不可用"))]
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
    run.add_argument("-o", "--out", default="var/out", help="输出目录 (默认 var/out)")
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
