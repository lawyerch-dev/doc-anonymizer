"""多模型对比基准: 同一批中文样例, 比较各模型的实体召回 / 耗时 / 内存。

用法:
    .venv/bin/python scripts/bench_models.py                # 自动扫描 models/*.gguf
    .venv/bin/python scripts/bench_models.py a.gguf b.gguf  # 指定模型

每个模型: 启动独立 llama-server -> 跑样例 -> 统计 -> 关闭。
需要 llama-server 在 PATH, 且端口 8091+ 空闲。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docanon.config import load_config  # noqa: E402
from docanon.detectors.dictionary import DictionaryDetector  # noqa: E402
from docanon.engines.llm.ner import LLMNERDetector  # noqa: E402
from docanon.engines.llm.client import LLMConfig, LLMError  # noqa: E402
from docanon.detectors.rule import RuleDetector  # noqa: E402
from docanon.contract import Block  # noqa: E402
from docanon.resolve import resolve_overlaps  # noqa: E402

# (文本, 必须被识别出的敏感片段)
CASES: list[tuple[str, set[str]]] = [
    ("汇报人：张三，联系电话 13812340000。", {"张三", "13812340000"}),
    ("客户是北京华信科技有限公司，对接人李四。", {"李四", "北京华信科技"}),
    ("合同金额 860000 元，签约地点在上海市浦东新区。", {"860000", "上海市浦东新区"}),
    ("项目负责人王五，身份证 110101199003071234。", {"王五", "110101199003071234"}),
    ("最终用户为赵六，邮箱 zhaoliu@example.com。", {"赵六", "zhaoliu@example.com"}),
    ("运维联系人孙七，服务器 IP 192.168.1.100，请勿外传。", {"孙七", "192.168.1.100"}),
]


def covered(expected: str, detected: list[str]) -> bool:
    return any(t and (expected in t or t in expected) for t in detected)


def detect_all(text: str, port: int, dictionary: list[str], timeout: int) -> list[str]:
    block = Block("b", text)
    llm = LLMNERDetector(
        LLMConfig(base_url=f"http://127.0.0.1:{port}/v1", model="bench",
                  timeout=timeout, disable_thinking=True)
    )
    found = RuleDetector().detect(block) + DictionaryDetector(dictionary).detect(block)
    try:
        found += llm.detect(block)
    except LLMError:
        pass  # 模型没答上就算零命中, 交给召回率体现
    return [d.span.text for d in resolve_overlaps(found)]


def _ready(port: int, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def start_server(model: Path, port: int, ctx: int = 4096):
    log = open(f"/tmp/llama_bench_{port}.log", "w")
    proc = subprocess.Popen(
        ["llama-server", "-m", str(model), "--alias", "bench", "-c", str(ctx),
         "-ngl", "99", "--host", "127.0.0.1", "--port", str(port)],
        stdout=log, stderr=subprocess.STDOUT,
    )
    if not _ready(port, 240):
        proc.terminate()
        raise RuntimeError(f"启动超时, 见 /tmp/llama_bench_{port}.log")
    return proc, log


def rss_mb(pid: int) -> float:
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)])
        return int(out.strip()) / 1024
    except Exception:
        return -1.0


def bench(model: Path, port: int, dictionary: list[str], timeout: int) -> dict:
    size_gb = model.stat().st_size / 1e9
    proc, log = start_server(model, port)
    try:
        detect_all(CASES[0][0], port, dictionary, timeout)  # warmup
        hit = need = 0
        times: list[float] = []
        misses: list[str] = []
        for text, expected in CASES:
            t = time.time()
            detected = detect_all(text, port, dictionary, timeout)
            times.append(time.time() - t)
            for e in expected:
                need += 1
                if covered(e, detected):
                    hit += 1
                else:
                    misses.append(e)
        mem = rss_mb(proc.pid)
        return {
            "model": model.name, "size_gb": size_gb, "port": port,
            "recall": hit / need if need else 0.0, "hit": hit, "need": need,
            "avg_s": sum(times) / len(times), "mem_mb": mem, "misses": misses,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
        log.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", help="模型 gguf 路径; 缺省扫描 var/models/*.gguf")
    args = parser.parse_args()

    models = [Path(m) for m in args.models] or sorted((ROOT / "models").glob("*.gguf"))
    if not models:
        print("没找到模型, 请先下载到 var/models/")
        return 1

    cfg = load_config()
    dictionary = cfg.dictionary
    print(f"样例数: {len(CASES)}  需要识别的片段总数: {sum(len(e) for _, e in CASES)}\n")

    results = []
    for i, model in enumerate(models):
        print(f"[{i+1}/{len(models)}] 测试 {model.name} ...", flush=True)
        try:
            results.append(bench(model, 8091 + i, dictionary, cfg.llm.timeout))
        except Exception as exc:  # noqa: BLE001
            print(f"  跳过: {exc}")

    print("\n" + "=" * 78)
    print(f"{'模型':<34}{'大小':>7}{'召回':>8}{'均耗时':>9}{'内存':>9}")
    print("-" * 78)
    for r in sorted(results, key=lambda x: (-x["recall"], x["avg_s"])):
        print(f"{r['model']:<34}{r['size_gb']:>6.1f}G{r['recall']*100:>7.1f}%"
              f"{r['avg_s']:>8.2f}s{r['mem_mb']:>7.0f}M")
    print("=" * 78)
    for r in results:
        if r["misses"]:
            print(f"{r['model']}: 漏掉 -> {', '.join(r['misses'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
