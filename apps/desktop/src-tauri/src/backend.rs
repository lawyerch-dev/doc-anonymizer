//! 拉起本地 Python 服务, 等它就绪再把窗口切过去 —— 失败一律说清原因, 不放空窗口干等。

use std::env;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Url, WebviewWindow};

use crate::paths;

/// 等多久算起不来。后端绑好端口就会答 /health(引擎预检是之后界面里的事), 所以正常是秒级;
/// 留这么宽是为了不与"机器慢/首次解压"较劲。
const READY_TIMEOUT: Duration = Duration::from_secs(120);

static BACKEND: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn slot() -> &'static Mutex<Option<Child>> {
    BACKEND.get_or_init(|| Mutex::new(None))
}

/// 窗口已经开出来了, 所以报错要报进窗口里 —— 从访达双击启动的人看不到 stderr。
pub fn boot(app: AppHandle, window: WebviewWindow) {
    if let Err(why) = start(&app, &window) {
        eprintln!("[docanon] {why}");
        let payload = serde_json::to_string(&why).unwrap_or_else(|_| "\"启动失败\"".to_string());
        let _ = window.eval(format!(
            "window.__docanonFail && window.__docanonFail({payload})"
        ));
    }
}

fn start(app: &AppHandle, window: &WebviewWindow) -> Result<(), String> {
    let root = paths::resolve_root(app)?;
    let data = paths::data_dir(root.packaged)?;
    let port: u16 = env::var("DOCANON_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8770);
    let config = env::var("DOCANON_CONFIG").unwrap_or_else(|_| "configs/onnx.yaml".to_string());
    let (program, args) = paths::launch(&root, &config, port);

    eprintln!(
        "[docanon] 资源根={}{} 运行方式={}",
        root.path.display(),
        match &data {
            Some(d) => format!(" 数据目录={}", d.display()),
            None => String::new(),
        },
        if program.contains("docanon-server") { "侧车" } else { "源码" },
    );

    let mut cmd = Command::new(&program);
    cmd.args(&args)
        .current_dir(&root.path)
        .env("DOCANON_ROOT", &root.path)
        // 壳被强杀时后端必须自己了断: 由 docanon_core/server/lifecycle.py 的父进程监视兜底
        .env("DOCANON_EXIT_WITH_PARENT", "1")
        .env("PATH", paths::backend_path())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());
    if let Some(dir) = &data {
        cmd.env("DOCANON_DATA", dir);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // 侧车是控制台子系统的程序, 不压住的话 Windows 上会多弹一个黑框
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let child = cmd
        .spawn()
        .map_err(|e| format!("起不了 Python 后端(`{program}`): {e}"))?;
    let mine = child.id();
    *slot().lock().map_err(|_| "内部状态锁坏了".to_string())? = Some(child);

    wait_healthy(port, mine, &program, &args)?;

    let url = format!("http://127.0.0.1:{port}");
    let target: Url = url
        .parse()
        .map_err(|e| format!("窗口地址不合法(`{url}`): {e}"))?;
    window
        .navigate(target)
        .map_err(|e| format!("窗口切不到 `{url}`: {e}"))
}

/// 等后端就绪。两条都不许省:
///   1. 自己拉起的那个进程死了就立刻停 —— 端口上还答着话的多半是别人的旧孤儿,
///      再等下去只会用别人的服务开出一个假窗口;
///   2. `/health` 报的 pid 必须是我拉起的那个 —— 对不上就用 DOCANON_PORT 换个端口,
///      否则关窗时杀的不是真正在服务的那个进程。
fn wait_healthy(port: u16, mine: u32, program: &str, args: &[String]) -> Result<(), String> {
    let deadline = Instant::now() + READY_TIMEOUT;
    loop {
        if let Some(code) = exited() {
            return Err(format!(
                "Python 后端已退出(退出码 {code})。直接跑 `{program} {}` 能看到具体原因",
                args.join(" ")
            ));
        }
        match health_pid(port) {
            Some(pid) if pid == mine => return Ok(()),
            Some(pid) => {
                return Err(format!(
                    "端口 {port} 上跑着另一个 docanon(pid={pid}), 本壳拉起的后端是 pid={mine}。\
                     先关掉它, 或用 DOCANON_PORT 换一个端口"
                ))
            }
            None => {}
        }
        if Instant::now() >= deadline {
            return Err(format!(
                "Python 服务启动超时({} 秒)。直接跑 `{program} {}` 看看卡在哪",
                READY_TIMEOUT.as_secs(),
                args.join(" ")
            ));
        }
        std::thread::sleep(Duration::from_millis(400));
    }
}

/// 自己的后端退出了吗(退出码; 被信号带走时拿不到码, 给 -1)。
fn exited() -> Option<i32> {
    let mut guard = slot().lock().ok()?;
    let child = guard.as_mut()?;
    match child.try_wait() {
        Ok(Some(status)) => Some(status.code().unwrap_or(-1)),
        _ => None,
    }
}

/// 关窗/退出前收尸。
///
/// 真正兜底的是后端自己的父进程监视: 壳被 SIGKILL 时这里根本不会执行, 而
/// `DOCANON_EXIT_WITH_PARENT` 会让后端发现父进程没了主动退出。
pub fn shutdown() {
    if let Ok(mut guard) = slot().lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// `/health` 答的是 `{"ok": true, "pid": 1234, ...}`。只需要 pid, 所以不引 HTTP 客户端,
/// 自己发一条最小的 GET —— 少一个依赖, 也就少一份要跟 Tauri 版本对齐的东西。
fn health_pid(port: u16) -> Option<u32> {
    let body = http_get(port)?;
    let at = body.find("\"pid\"")? + "\"pid\"".len();
    let rest = &body[at..];
    let colon = rest.find(':')? + 1;
    let digits: String = rest[colon..]
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}

fn http_get(port: u16) -> Option<String> {
    let addr: SocketAddr = format!("127.0.0.1:{port}").parse().ok()?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(800)).ok()?;
    stream
        .set_read_timeout(Some(Duration::from_millis(2000)))
        .ok()?;
    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).ok()?;
    let mut raw = String::new();
    stream.read_to_string(&mut raw).ok()?;
    let head = raw.find("\r\n\r\n")? + 4;
    Some(raw[head..].to_string())
}
