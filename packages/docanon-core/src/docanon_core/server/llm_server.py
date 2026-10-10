"""托管本地大模型服务: 用户选了哪个模型, 就直接用它 —— 不用自己去终端起 llama-server。

之前"选模型"之后还要用户复制一行 `serve_llm.sh` 去终端跑, 等于把安装与启动的责任推回给用户。
这里由后端在**开跑之前**把服务弄就绪: 没起就起、换了模型就换、已经在跑就复用; 起不来一律抛
`LLMServerError` 并带上原因, 绝不静默跳过这一层(见 `05-security.md` 第一条)。

只服务 Web 这条路径: CLI 是一次性进程, 不该在背后留一个常驻服务(模型几个 G, 停了再起很贵)。

进程内只托管一个 llama-server(本机单人用); 端口默认 `8090`, 可用 `DOCANON_LLM_PORT` 改。
端口上已经有服务在应答时**不抢占**: 正好是我们要的模型就复用(例如上一次没退干净的孤儿),
是别的就用下一个空闲端口 —— 别人的服务不该被我们杀掉。
"""
from __future__ import annotations

import atexit
import collections
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

from . import downloads

ENV_PORT = "DOCANON_LLM_PORT"
DEFAULT_PORT = 8090
_CTX = "8192"
_NGL = "99"
_BOOT_TIMEOUT = 120.0   # 首次加载 2-3G 的 gguf 要几秒到几十秒
_KILL_GRACE = 5.0
_LOG_LINES = 60


class LLMServerError(RuntimeError):
    """服务起不来(没装 llama.cpp / 模型没下 / 启动失败)。带一句用户能照做的话。"""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


_lock = threading.Lock()
_child: subprocess.Popen | None = None
_child_model: str = ""      # 目录里的 id
_child_port: int = 0
_child_error: str = ""
_log: collections.deque = collections.deque(maxlen=_LOG_LINES)


# ---------- 查询 ----------

def _binary() -> str | None:
    return shutil.which("llama-server")


def _probe(port: int, timeout: float = 2.0) -> list[str] | None:
    """`/v1/models` 返回的模型别名; 没应答就是 None(不是空列表 —— 那是"答了但没有模型")。"""
    url = f"http://127.0.0.1:{port}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 没起来 / 不是 OpenAI 兼容服务, 都算"没应答"
        return None
    return [str(m.get("id", "")) for m in data.get("data", [])]


def _free_port(start: int, tries: int = 20) -> int:
    for port in range(start, start + tries):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise LLMServerError(f"{start}~{start + tries - 1} 都占着, 找不到可用端口", code=500)


def _preferred_port() -> int:
    raw = os.environ.get(ENV_PORT, "").strip()
    return int(raw) if raw.isdigit() else DEFAULT_PORT


def _drain(proc: subprocess.Popen) -> None:
    """把 llama-server 的 stderr 收进环形缓冲: 启动失败时要拿它给用户一个原因。"""
    stream = proc.stderr
    if stream is None:
        return
    try:
        for line in stream:
            _log.append(line.rstrip())
    except Exception:  # noqa: BLE001 - 管道被关掉(进程没了)就收工
        pass


def _tail() -> str:
    return " / ".join(list(_log)[-6:]) if _log else ""


# ---------- 生命周期 ----------

def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=_KILL_GRACE)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=_KILL_GRACE)


def _clear_child_locked() -> None:
    """清掉"当前托管进程"(不碰 `_child_error`: 失败原因要留给人看)。调用方持锁。"""
    global _child, _child_model, _child_port
    if _child is not None:
        _kill(_child)
    _child = None
    _child_model = ""
    _child_port = 0
    _log.clear()


def _adopt_reused_locked(port: int, model_id: str) -> None:
    """记住一个"不是我们起的、但正好是我们要的模型"的服务(关掉时不用去杀它)。调用方持锁。"""
    global _child_model, _child_port, _child_error
    _clear_child_locked()
    _child_model = model_id
    _child_port = port
    _child_error = ""


def stop() -> None:
    """停掉我们起的那个服务(没起就是空操作)。"""
    global _child_error
    with _lock:
        _clear_child_locked()
        _child_error = ""


def status() -> dict:
    with _lock:
        if _child is not None and _child.poll() is None:
            return {"state": "running", "model_id": _child_model, "port": _child_port, "error": ""}
        # 复用来的服务(不是我们起的, 所以没有 `_child`): 还答话就算 running
        if _child_port and _child_model in (_probe(_child_port) or []):
            return {"state": "running", "model_id": _child_model, "port": _child_port, "error": ""}
        return {
            "state": "error" if _child_error else "idle",
            "model_id": _child_model,
            "port": _child_port,
            "error": _child_error,
        }


def _base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/v1"


def _info() -> dict:
    return {
        "base_url": _base_url(_child_port),
        "alias": _child_model,
        "port": _child_port,
        "pid": _child.pid if _child is not None else None,
    }


def _spawn_locked(binary: str, model_path, model_id: str, port: int) -> None:
    """起一个新进程并等它就绪; 超时或进程自己死了都抛错(带 stderr 尾巴)。调用方持锁。"""
    global _child, _child_model, _child_port, _child_error
    cmd = [
        binary, "-m", str(model_path), "--alias", model_id,
        "-c", _CTX, "-ngl", _NGL, "--host", "127.0.0.1", "--port", str(port),
    ]
    _log.clear()
    # encoding 必须显式给: text=True 会按 locale 解码, Windows 上那是 cp1252 —— llama-server 的
    # 日志里一旦有非 ASCII(路径、中文提示), 读取就抛 UnicodeDecodeError(同一个根因, 见 cli 的
    # _ensure_utf8_output)。errors="replace": 读日志是为了给用户一个原因, 不该因编码再崩一次。
    _child = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    _child_model = model_id
    _child_port = port
    _child_error = ""
    threading.Thread(target=_drain, args=(_child,), name="llama-server-log", daemon=True).start()

    deadline = time.monotonic() + _BOOT_TIMEOUT
    while time.monotonic() < deadline:
        if _child.poll() is not None:
            reason = f"llama-server 启动即退出: {_tail()}"
            _clear_child_locked()
            _child_error = reason
            raise LLMServerError(reason, code=500)
        if _probe(port):
            return
        time.sleep(0.3)

    reason = f"等了 {int(_BOOT_TIMEOUT)} 秒还没就绪: {_tail()}"
    _clear_child_locked()
    _child_error = reason
    raise LLMServerError(reason, code=500)


def ensure(model_id: str) -> dict:
    """确保"这个模型"的服务在跑, 返回它的地址与别名。

    换了模型就把旧的停掉再起(同一时刻只留一个, 否则两个 3G 的模型会一起占内存)。
    """
    item = downloads.entry(model_id)          # 未知 id → DownloadError(带原因)
    if not downloads.is_downloaded(item):
        raise LLMServerError(
            f"「{item['name']}」还没安装 —— 先在设置里点「安装」（{item['size_gb']} GB）"
        )
    model_path = downloads.model_path(item)

    with _lock:
        # 1) 我们自己起的、还是这个模型、还活着 → 直接用
        if _child is not None and _child.poll() is None and _child_model == model_id and _probe(_child_port):
            return _info()

        # 2) 端口上已经有服务在应答, 而且正好是我们要的别名 → 复用它(别重复占内存, 也别打断别人的)
        port = _preferred_port()
        if model_id in (_probe(port) or []):
            _adopt_reused_locked(port, model_id)
            return _info()

        # 3) 起一个新的
        binary = _binary()
        if not binary:
            raise LLMServerError(
                "本机没有 llama-server —— 需要装 llama.cpp（macOS: brew install llama.cpp）",
                code=500,
            )
        _clear_child_locked()
        _spawn_locked(binary, model_path, model_id, _free_port(port))
        return _info()


def _atexit_stop() -> None:  # pragma: no cover - 进程退出路径, 单独测不了
    stop()


atexit.register(_atexit_stop)
