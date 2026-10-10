//! 资源根、可写数据目录、侧车启动命令。
//!
//! 这三件事都是"猜错就静默跑错东西"的地方(拿系统 python3 起后端、把模型写进只读的安装目录、
//! 用别人的旧孤儿开窗), 所以每一条都显式判断、失败就带原因返回, 不猜。

use std::env;
use std::ffi::OsString;
use std::path::{Path, PathBuf};

use tauri::{AppHandle, Manager};

/// 打包态资源根在包里的目录名 —— 必须与 `bundle.resources` 的目标名一致
const PACKAGED_DIR: &str = "docanon";
/// 源码态的标记: 有它就是个能跑的仓库
const DEV_MARKER: &str = "configs/default.yaml";
/// 打包态的标记: 资源根被收进了包内的 `docanon/`(它自带 sidecar, 不需要 .venv, 也不需要仓库)
const PACKAGED_MARKER: &str = "docanon/configs/default.yaml";

pub struct Root {
    pub path: PathBuf,
    /// 打包态: 可写状态必须挪到用户目录 —— 包内是只读的, 升级还会连它一起清掉
    pub packaged: bool,
}

fn root_at(dir: &Path) -> Option<Root> {
    if dir.join(PACKAGED_MARKER).is_file() {
        return Some(Root {
            path: dir.join(PACKAGED_DIR),
            packaged: true,
        });
    }
    if dir.join(DEV_MARKER).is_file() {
        return Some(Root {
            path: dir.to_path_buf(),
            packaged: false,
        });
    }
    None
}

fn find_root(start: &Path) -> Option<Root> {
    let mut dir: Option<&Path> = Some(start);
    while let Some(d) = dir {
        if let Some(hit) = root_at(d) {
            return Some(hit);
        }
        dir = d.parent();
    }
    None
}

/// 打包态的兜底: 壳自己就住在包的可执行文件目录里, 资源根在它附近的资源目录下。
/// 两个平台的资源目录不一样(macOS 是 `Contents/Resources`, Windows 与可执行文件同级),
/// 而且都可能是它下面的 `app/` —— 逐个试一遍, 试错的代价只是几次 stat。
fn from_bundle(app: &AppHandle) -> Option<Root> {
    let mut bases: Vec<PathBuf> = Vec::new();
    if let Ok(res) = app.path().resource_dir() {
        if let Some(parent) = res.parent() {
            bases.push(parent.to_path_buf());
        }
        bases.push(res);
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            // macOS 的 .app 就这一种布局: 可执行文件在 Contents/MacOS, 资源在同级 Contents/Resources。
            // 这里按布局再指一遍, 不完全押在 resource_dir() 上 —— 它是 Tauri 的内部实现,
            // 而这些候选路径试错的代价只是几次 stat; 反过来押错一次的代价是"装完了打不开"。
            bases.push(dir.join("Resources"));
            if let Some(parent) = dir.parent() {
                bases.push(parent.join("Resources"));
                bases.push(parent.to_path_buf());
            }
            bases.push(dir.to_path_buf());
        }
    }
    for base in bases {
        for rel in [None, Some("app")] {
            let dir = match rel {
                Some(r) => base.join(r),
                None => base.clone(),
            };
            if let Some(hit) = root_at(&dir) {
                return Some(hit);
            }
        }
    }
    None
}

/// 资源根是**找出来的, 不是数 `..` 出来的**: dev 构建产物在 `src-tauri/target/<profile>/` 里面,
/// 层数随 profile 变, 猜错的后果是拿系统 python3 去起后端(报一堆 ModuleNotFoundError)。
pub fn resolve_root(app: &AppHandle) -> Result<Root, String> {
    if let Some(dir) = env::var_os("DOCANON_ROOT") {
        let path = PathBuf::from(dir);
        let packaged = path.join(PACKAGED_DIR).is_dir();
        return Ok(Root { path, packaged });
    }
    if let Some(hit) = env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().and_then(find_root))
    {
        return Ok(hit);
    }
    from_bundle(app).ok_or_else(|| {
        format!(
            "找不到资源根(向上查找 {DEV_MARKER} 与 {PACKAGED_MARKER} 都没有)。\
             源码树里跑请确认 configs/default.yaml 还在; 打包运行时请设置 DOCANON_ROOT 指向资源根。"
        )
    })
}

/// 可写状态根(下载到的模型、用户自建方案)。
///
/// 分家的理由: 打包后资源根在安装目录内部, 首次运行还可能被 macOS 的 App Translocation
/// 挂到只读的随机路径上 —— 模型写到那儿不是失败就是被清掉。
/// 源码态返回 `None`: 一切照旧落在仓库的 `var/` 下, 不打扰改代码的人。
pub fn data_dir(packaged: bool) -> Result<Option<PathBuf>, String> {
    if let Some(dir) = env::var_os("DOCANON_DATA") {
        let path = PathBuf::from(dir);
        return ensure_dir(path).map(Some);
    }
    if !packaged {
        return Ok(None);
    }

    let home = env::var_os("HOME").map(PathBuf::from);
    let path = if cfg!(windows) {
        let base = env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .or_else(|| env::var_os("USERPROFILE").map(PathBuf::from))
            .or_else(|| home.as_ref().map(|h| h.join("AppData").join("Local")))
            .ok_or_else(|| "既没有 LOCALAPPDATA 也没有 USERPROFILE —— 定位不了数据目录".to_string())?;
        base.join(PACKAGED_DIR)
    } else if cfg!(target_os = "macos") {
        home.ok_or_else(|| "没有 HOME —— 定位不了数据目录".to_string())?
            .join("Library")
            .join("Application Support")
            .join(PACKAGED_DIR)
    } else {
        env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| home.as_ref().map(|h| h.join(".local").join("share")))
            .ok_or_else(|| "既没有 HOME 也没有 XDG_DATA_HOME —— 定位不了数据目录".to_string())?
            .join(PACKAGED_DIR)
    };
    ensure_dir(path).map(Some)
}

fn ensure_dir(path: PathBuf) -> Result<PathBuf, String> {
    std::fs::create_dir_all(&path).map_err(|e| format!("建不了数据目录 {}: {e}", path.display()))?;
    Ok(path)
}

/// 后端怎么起、给什么参数。三条路(侧车 / venv / 系统 python)给的是**同一串参数** ——
/// 侧车的入口就是 `docanon_core.cli:main`, 所以换解释器或换可执行文件都不用改调用代码。
pub fn launch(root: &Root, config: &str, port: u16) -> (String, Vec<String>) {
    let web = || {
        vec![
            "web".to_string(),
            "--no-browser".to_string(),
            "-p".to_string(),
            port.to_string(),
            "-c".to_string(),
            config.to_string(),
        ]
    };
    let as_module = |mut rest: Vec<String>| {
        let mut all = vec!["-m".to_string(), "docanon_core.cli".to_string()];
        all.append(&mut rest);
        all
    };

    if let Some(python) = env::var_os("DOCANON_PYTHON") {
        return (python.to_string_lossy().into_owned(), as_module(web()));
    }
    if let Some(exe) = sidecar(root) {
        return (exe, web());
    }
    // Windows 的 venv 把可执行文件放在 Scripts/ 下, 名字也不一样
    let venv = root.path.join(".venv").join(if cfg!(windows) {
        "Scripts/python.exe"
    } else {
        "bin/python"
    });
    if venv.is_file() {
        return (venv.to_string_lossy().into_owned(), as_module(web()));
    }
    eprintln!(
        "[docanon] 既没有打包侧车({}/sidecar)也没有 {} —— 退回 python3, \
         它必须能 import docanon(没装就会启动失败)。建议设置 DOCANON_PYTHON。",
        root.path.display(),
        venv.display()
    );
    ("python3".to_string(), as_module(web()))
}

/// Windows 的产物带 `.exe`, 所以两个名字都试: 只认一个的话会静默退到系统 python3 上,
/// 报一堆 ModuleNotFoundError —— 那是"看着起来了、其实什么都没起来"的假故障。
fn sidecar(root: &Root) -> Option<String> {
    for name in ["docanon-server", "docanon-server.exe"] {
        let candidate = root.path.join("sidecar").join(name);
        if candidate.is_file() {
            return Some(candidate.to_string_lossy().into_owned());
        }
    }
    None
}

/// 从访达双击启动时, macOS 给的 PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin` —— 而 `llama-server`
/// 与 `soffice` 都是用户自己装的(brew 在 `/opt/homebrew/bin`), 不补上就会出现"终端里明明装了,
/// 双击却说没有"。Windows 拿的是注册表里的用户+系统 PATH, 没这个问题。
pub fn backend_path() -> OsString {
    let mut parts: Vec<OsString> = Vec::new();
    if let Some(existing) = env::var_os("PATH") {
        parts.extend(env::split_paths(&existing).filter(|p| !p.as_os_str().is_empty()).map(|p| p.into_os_string()));
    }
    if cfg!(target_os = "macos") {
        parts.push(OsString::from("/opt/homebrew/bin"));
        parts.push(OsString::from("/usr/local/bin"));
    }
    // 分隔符用平台自己的(Windows 是 `;`), 硬写 `:` 会把整条 PATH 弄坏
    env::join_paths(parts).unwrap_or_else(|_| OsString::from("/usr/bin:/bin"))
}
