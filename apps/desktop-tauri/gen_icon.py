"""生成占位应用图标: 白底 + 涂黑条, 呼应"脱敏"。产物交给 `cargo tauri icon` 出全套图标。

用法: .venv/bin/python apps/desktop-tauri/gen_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).resolve().parent / "app-icon.png"

img = Image.new("RGB", (SIZE, SIZE), "#f5f6f8")
d = ImageDraw.Draw(img)

# 仿正文行: 浅灰细条; 敏感片段: 黑色涂黑块
rows = [
    (0.18, 0.70, False),
    (0.28, 0.62, False),
    (0.38, 0.30, True),   # 涂黑
    (0.48, 0.55, False),
    (0.58, 0.42, True),   # 涂黑
    (0.68, 0.66, False),
    (0.78, 0.34, True),   # 涂黑
]
h = int(SIZE * 0.045)
for top, width, redacted in rows:
    y = int(SIZE * top)
    x0 = int(SIZE * 0.16)
    x1 = int(SIZE * (0.16 + width * 0.68))
    d.rounded_rectangle([x0, y, x1, y + h], radius=h // 2, fill="#111111" if redacted else "#c9ced6")

img.save(OUT)
print(OUT)
