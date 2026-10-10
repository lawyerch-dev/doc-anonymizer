# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 规格: 把五个 docanon 包 + 推理依赖打成桌面壳能直接跑的侧车。

macOS 与 Windows 都用这一份(spec 在哪个平台跑就出哪个平台的原生可执行文件 —— PyInstaller
**不做交叉编译**, 所以 Windows 的包只能在 Windows 上打, 见 .github/workflows/build-desktop.yml)。

为什么用 **onedir 而不是 onefile**: 壳会校验"端口上答话的 pid 是不是我拉起的那个子进程"
(见 apps/desktop/src/bun/index.ts 的 waitForServer)。onefile 的引导器会先解包再 fork 出真正的
进程, 于是 child.pid 与 /health 报的 pid 对不上, 壳会当成"端口被别的实例占了"直接退出。
onedir 只有一个进程, 天然对得上, 启动也快得多。

侧车**不带资源**(configs/ web/ samples/ vendor/): 那些由 scripts/dev.sh dist 单独摆进
资源根, 侧车只负责代码与依赖 —— 与 resources.py 里"不做 wheel 自包含"的部署契约同源。
"""
import pathlib

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = pathlib.Path(SPECPATH).resolve()   # apps/desktop/sidecar
DESKTOP = SPEC_DIR.parent                     # apps/desktop
REPO = DESKTOP.parent.parent                  # 仓库根

# 五个包都从源码目录直接分析: 此处**不能**依赖 editable 安装的 finder,
# 否则换个没跑过 pip install -e 的环境就会静默打出一个 import 不了 docanon 的侧车。
PACKAGES = (
    "docanon-contract",
    "docanon-engine-ocr",
    "docanon-engine-ner-onnx",
    "docanon-engine-ner-llm",
    "docanon-core",
)

datas, binaries, hiddenimports = [], [], []

# rapidocr 没有官方 hook, 而它的 config.yaml / default_models.yaml / OCR 权重都在包目录里 ——
# 少一个就是"引擎起不来", 所以整包收进去(约 30MB, 换来 OCR 离线可用)。
for pkg in ("rapidocr",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 引擎是按名字动态构造的(detectors.DETECTORS / extractors.extractor_classes), 静态分析看不全
for pkg in ("docanon_contract", "docanon_engine_ocr", "docanon_engine_ner_onnx",
            "docanon_engine_ner_llm", "docanon_core"):
    hiddenimports += collect_submodules(pkg)

a = Analysis(
    [str(SPEC_DIR / "entry.py")],
    pathex=[str(REPO / "packages" / p / "src") for p in PACKAGES],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 测试与基准用的依赖(pytest/reportlab)不该进包
    excludes=["pytest", "reportlab", "matplotlib", "tkinter", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="docanon-server",
    debug=False,
    strip=False,
    upx=False,
    # Windows 上要留控制台子系统: 壳用 windowsHide 去压掉那个黑框(见 index.ts), 而控制台的句柄
    # 正是侧车日志的出口 —— 关成 windowed 反而会让 print 无处可写(entry.py 里还得为此兜一层)。
    console=True,
    # macOS 专属; 非 Darwin 平台 PyInstaller 会直接忽略它(自己按宿主架构来), 所以不用分支
    target_arch="arm64",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="docanon-server",
)
