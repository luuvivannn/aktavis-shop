"""One-off: produce a 640x360 BotFather Mini App preview from a source image."""
from pathlib import Path
from PIL import Image

SRC = Path(r"C:\Users\user\Pictures\Screenshots\Снимок экрана 2026-05-27 131319.png")
DST = Path(r"C:\Users\user\Desktop\telegram bot clothes\aktavis_miniapp_640x360.jpg")

TARGET_W, TARGET_H = 640, 360

img = Image.open(SRC).convert("RGB")
src_w, src_h = img.size

target_ratio = TARGET_W / TARGET_H
src_ratio = src_w / src_h

if src_ratio > target_ratio:
    new_w = int(src_h * target_ratio)
    left = (src_w - new_w) // 2
    img = img.crop((left, 0, left + new_w, src_h))
else:
    new_h = int(src_w / target_ratio)
    top = (src_h - new_h) // 2
    img = img.crop((0, top, src_w, top + new_h))

img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
img.save(DST, "JPEG", quality=92, optimize=True)

print(f"OK: {DST}  ({DST.stat().st_size} bytes)  size={img.size}")
