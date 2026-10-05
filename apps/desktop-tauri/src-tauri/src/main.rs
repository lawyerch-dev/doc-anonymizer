//! doc-anonymizer 桌面壳 (Tauri / WKWebView)
//!
//! 职责与 apps/desktop/main.js 一致: 拉起本地 Python 服务 (docanon web) → 等服务就绪 →
//! 打开窗口加载它; 退出时回收 Python 子进程。
//!
//! 可通过环境变量覆盖:
//!   DOCANON_PYTHON  Python 解释器 (默认 <root>/.venv/bin/python, 退回 python3)
//!   DOCANON_ROOT    项目根目录 (默认按源码位置推断)
//!   DOCANON_CONFIG  配置文件 (默认 configs/onnx.yaml)
//!   DOCANON_PORT    服务端口 (默认 8772)
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

/// 持有 Python 子进程, 供退出时回收。
struct PythonServer(Mutex<Option<Child>>);

fn var_or(key: &str, fallback: &str) -> String {
    env::var(key).unwrap_or_else(|_| fallback.to_string())
}

fn project_root() -> PathBuf {
    if let Some(explicit) = env::var_os("DOCANON_ROOT") {
        return PathBuf::from(explicit);
    }
    // src-tauri -> desktop-tauri -> apps -> 项目根
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("..")
        .to_path_buf()
}

fn python_bin(root: &Path) -> String {
    if let Some(explicit) = env::var_os("DOCANON_PYTHON") {
        return explicit.to_string_lossy().into_owned();
    }
    let venv = root.join(".venv").join("bin").join("python");
    if venv.exists() {
        venv.to_string_lossy().into_owned()
    } else {
        "python3".to_string()
    }
}

fn start_server(root: &Path, python: &str, port: u16, config: &str) -> Result<Child, String> {
    Command::new(python)
        .args(["-m", "docanon.cli", "web", "--no-browser"])
        .arg("-p")
        .arg(port.to_string())
        .arg("-c")
        .arg(config)
        .current_dir(root)
        .env("PYTHONPATH", root.join("src"))
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|e| format!("拉起 {python} 失败: {e}"))
}

/// 用裸 HTTP 请求探活, 避免为此引入 http 客户端依赖。
/// server.py 基于 BaseHTTPRequestHandler, 状态行可能是 HTTP/1.0, 所以只看状态码。
fn healthy(port: u16) -> bool {
    let addr = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(800)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let request = format!("GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut status_line = String::new();
    match BufReader::new(stream).read_line(&mut status_line) {
        Ok(n) if n > 0 => status_line.split_whitespace().nth(1) == Some("200"),
        _ => false,
    }
}

fn wait_for_server(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if healthy(port) {
            return true;
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}

fn stop_server(app: &AppHandle) {
    if let Some(state) = app.try_state::<PythonServer>() {
        if let Some(mut child) = state.0.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn main() {
    let port: u16 = var_or("DOCANON_PORT", "8772").parse().unwrap_or(8772);
    let config = var_or("DOCANON_CONFIG", "configs/onnx.yaml");
    let root = project_root();
    let python = python_bin(&root);
    let url = format!("http://127.0.0.1:{port}");

    tauri::Builder::default()
        .manage(PythonServer(Mutex::new(None)))
        .setup(move |app| {
            let child = start_server(&root, &python, port, &config)?;
            *app.state::<PythonServer>().0.lock().unwrap() = Some(child);

            if wait_for_server(port, Duration::from_secs(60)) {
                println!("[shell] Python 服务已就绪: {url}");
            } else {
                eprintln!("[shell] 服务启动超时, 窗口仍会打开, 页面可能报错");
            }

            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url.parse().expect("合法的 http 地址")))
                .title("文档脱敏工具")
                .inner_size(1280.0, 860.0)
                .resizable(true)
                .build()?;
            Ok(())
        })
        // 关窗即退出: 不留无窗口的常驻服务 (它带 /health 与 mapping 接口, 属于泄露面)
        .on_window_event(|window, event| {
            if let WindowEvent::Destroyed = event {
                window.app_handle().exit(0);
            }
        })
        .build(tauri::generate_context!())
        .expect("构建 Tauri 应用失败")
        .run(move |app, event| {
            if let tauri::RunEvent::Exit = event {
                stop_server(app);
            }
        });
}
