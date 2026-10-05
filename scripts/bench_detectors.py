"""检测后端对比: ONNX 中文 NER vs 生成式 LLM, 同一批中文样例。

用法:
    .venv/bin/python scripts/bench_detectors.py                 # 有 llama-server(:8080) 时同时比 LLM
    .venv/bin/python scripts/bench_detectors.py --no-llm        # 只比 ONNX
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from bench_models import CASES, covered  # noqa: E402  复用样例与覆盖判定
from docanon.config import LLMConfig, load_config  # noqa: E402
from docanon.detectors.dictionary import DictionaryDetector  # noqa: E402
from docanon.detectors.llm_ner import LLMNERDetector  # noqa: E402
from docanon.detectors.onnx_ner import OnnxNERDetector  # noqa: E402
from docanon.detectors.rule import RuleDetector  # noqa: E402
from docanon.models import Block  # noqa: E402
from docanon.resolve import resolve_overlaps  # noqa: E402


def rss_mb() -> float:
    import subprocess

    out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(__import__("os").getpid())])
    return int(out.strip()) / 1024


def run_backend(name: str, detectors, dictionary: list[str]) -> dict:
    base = time.time()
    dets = detectors + [RuleDetector(), DictionaryDetector(dictionary)]

    def one(text: str) -> list[str]:
        block = Block("b", text)
        found = []
        for d in dets:
            found.extend(d.detect(block))
        return [x.span.text for x in resolve_overlaps(found)]

    one(CASES[0][0])  # warmup
    mem0 = rss_mb()
    hit = need = 0
    times: list[float] = []
    misses: list[str] = []
    for text, expected in CASES:
        t = time.time()
        got = one(text)
        times.append(time.time() - t)
        for e in expected:
            need += 1
            if covered(e, got):
                hit += 1
            else:
                misses.append(e)
    return {
        "name": name, "recall": hit / need, "hit": hit, "need": need,
        "avg_ms": 1000 * sum(times) / len(times), "misses": misses,
        "load_s": base and (time.time() - base - sum(times)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080/v1")
    args = parser.parse_args()

    cfg = load_config()
    dictionary = cfg.dictionary
    backends: list[tuple[str, list]] = []

    for label, d in [("ONNX pii-engineer", "models/onnx/pii-engineer"),
                     ("ONNX gyr66(CLUENER)", "models/onnx/gyr66")]:
        p = ROOT / d
        if (p / "model.onnx").exists():
            try:
                backends.append((label, [OnnxNERDetector(p)]))
            except Exception as exc:  # noqa: BLE001
                print(f"加载失败 {label}: {exc}")
        else:
            print(f"跳过 {label}: 未下载 {p}")

    if not args.no_llm:
        llm = LLMNERDetector(LLMConfig(base_url=args.llm_url, model="qwen3.8-4b",
                                       timeout=120, disable_thinking=True))
        if llm.client.health():
            backends.append(("LLM Qwen3.8-4B", [llm]))
        else:
            print("跳过 LLM: 未检测到 llama-server")

    if not backends:
        print("没有可用后端")
        return 1

    print(f"样例 {len(CASES)} 个, 待识别片段 {sum(len(e) for _, e in CASES)} 个\n")
    results = [run_backend(n, ds, dictionary) for n, ds in backends]

    print("=" * 72)
    print(f"{'后端':<26}{'召回':>8}{'命中':>8}{'均耗时':>10}")
    print("-" * 72)
    for r in sorted(results, key=lambda x: (-x["recall"], x["avg_ms"])):
        print(f"{r['name']:<26}{r['recall']*100:>7.1f}%{r['hit']:>5}/{r['need']:<3}{r['avg_ms']:>8.0f}ms")
    print("=" * 72)
    for r in results:
        if r["misses"]:
            print(f"{r['name']}: 漏 -> {', '.join(r['misses'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
