"""共享 fixture(仓库根 conftest, 所有包的测试与根 tests/ 都能用)。

"测试怎么找仓库根 / 怎么起一个真服务"只留一种写法。

注意: 这里**不许在模块顶层 import docanon_* ** —— 那会让"只跑文档与包边界测试"也必须先装齐
五个包(CI 的部署门禁就靠这个特性)。


样板原本散在每个测试文件里(各自算 `REPO_ROOT`、各自 `ThreadingHTTPServer`、各自塞 PYTHONPATH),
加一个测试就要再抄一遍; 收敛到这里, 也让"测试跑在什么根上"这件事只有一个答案。
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import threading
from http.server import ThreadingHTTPServer
from typing import Iterator

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent  # 本文件就在仓库根

# 反假绿开关: 引擎测试在缺模型/缺可选依赖时会 skip, 于是"全绿"可能掩盖"引擎一次都没跑"。
# 设成 1 表示"这个环境的模型与可选依赖是齐备的", 那任何跳过都按失败处理(`npm run test:strict`)。
# 借鉴 DeepSeek Harness: 自跳过的套件必须有人证明它真的跑了, 不能靠"绿"。
REQUIRE_FULL_ENV = "DOCANON_REQUIRE_ENGINES"
_SKIPS: list[tuple[str, str]] = []


def _skip_reason(report) -> str:
    """把 pytest 的 longrepr 压成一句人话(它有时是 ('路径', 行号, 'Skipped: 原因') 这种元组)。"""
    text = str(report.longrepr or "")
    match = re.search(r"Skipped:[^\]'\")]*", text) or re.search(r"skip[^\]'\")]*", text, re.I)
    if match:
        return match.group(0).strip()
    tail = [line.strip() for line in text.splitlines() if line.strip()]
    return tail[-1] if tail else "skipped"


def pytest_runtest_logreport(report) -> None:
    if report.skipped:
        _SKIPS.append((report.nodeid, _skip_reason(report)))


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    """仓库根(也是资源根): 需要断言"文件在不在/相对路径对不对"的测试用它。"""
    return REPO_ROOT


@pytest.fixture
def ephemeral_server(tmp_path, monkeypatch) -> Iterator[str]:
    """起一个真的 HTTP 服务(随机端口, 用完即关), 返回 base URL。

    服务的 `out_root` 指向 tmp_path, 所以测试要把上传件/产物放进 `tmp_path/uploads/...`
    或 `tmp_path/outputs/...` 就能被访问到。

    `docanon_core` 在函数里才 import: 文档/架构这类测试不需要装 Python 包也能跑
    (CI 里只装 pytest+pyyaml 就跑得动文档漂移与包边界门禁)。
    """
    from docanon_core import server
    from docanon_core.config import load_config
    from docanon_core.server import profiles

    monkeypatch.setattr(server.Handler, "out_root", tmp_path)
    monkeypatch.setattr(server.Handler, "config", load_config())
    # serve() 会记住启动用的配置名(前端要标"当前口径"), 测试里对齐一下
    monkeypatch.setattr(server.Handler, "config_name", "default.yaml")
    # 用户配置落盘到 tmp_path: 测试不会读到/污染真实的 var/configs
    monkeypatch.setattr(profiles, "user_dir", lambda: tmp_path / "var" / "configs")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus) -> None:
    """DOCANON_REQUIRE_ENGINES=1 时, 任何 skip 都让整轮失败(并说清是哪几条、为什么跳)。"""
    if os.environ.get(REQUIRE_FULL_ENV) != "1" or not _SKIPS:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = [f"{REQUIRE_FULL_ENV}=1 声明了环境齐备, 但有 {len(_SKIPS)} 条测试被跳过 —— 这是假绿:"]
    lines += [f"  - {nodeid}\n      {reason}" for nodeid, reason in _SKIPS[:20]]
    if len(_SKIPS) > 20:
        lines.append(f"  …还有 {len(_SKIPS) - 20} 条")
    lines.append("  装齐模型与可选依赖(`npm run models` / `npm run setup`)后重跑; 或去掉这个环境变量。")
    text = "\n".join(lines)
    if reporter is not None:
        reporter.write_sep("=", "反假绿门禁", red=True)
        reporter.write_line(text, red=True)
    else:  # pragma: no cover - 只在没有终端插件时走到
        print(text, file=sys.stderr)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
