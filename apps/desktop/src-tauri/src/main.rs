// Tauri 桌面壳: 拉起本地 Python 服务(docanon web) → 窗口加载它(系统 WebView)。
//
// 与上一个壳(Electrobun)职责完全相同, 只是换了个不自解包、工具链更主流的运行时:
//   找资源根 → 定可写数据目录 → 找侧车 → spawn → 等 /health 就绪 → 窗口切过去 → 关窗收尸
// 这几步每一条都是踩出来的(见 apps/desktop/README.md), 换壳不许把它们丢掉。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod paths;

use tauri::menu::Menu;
use tauri::{WebviewUrl, WebviewWindowBuilder};

fn main() {
    let app = tauri::Builder::default()
        // macOS 不给菜单就等于没有 ⌘Q/⌘W —— 用系统标准菜单, 别自己手搓一遍
        .menu(|handle| Menu::default(handle))
        .setup(|app| {
            let handle = app.handle().clone();
            // 先把窗口开出来(加载本地启动页), 后台等后端就绪后再切过去。
            // 反过来做(等就绪再开窗)在首次使用时要黑着屏等一分钟 —— 那看起来就是双击没反应。
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("文档脱敏工具")
                .inner_size(1280.0, 860.0)
                .build()?;
            std::thread::spawn(move || backend::boot(handle, window));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Tauri 初始化失败");

    app.run(|_, event| {
        // 关窗即退出(单窗口工具), 退出前收走 Python 侧车
        if let tauri::RunEvent::Exit = event {
            backend::shutdown();
        }
    });
}
