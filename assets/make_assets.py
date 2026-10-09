#!/usr/bin/env python3
"""Generate all app artwork from assets/icon-source.jpg.

The source JPEG has its transparency flattened as a light checkerboard.
This script keys that background out with a border-seeded flood fill
(the icon's own white areas are fully enclosed, so they survive), then
emits:

  assets/icon.png               1024px master, transparent
  assets/hicolor/<s>x<s>/apps/<app>.png   freedesktop icon sizes
  assets/banner.png             1600x500 README/social banner
  flatpak_batch_installer/data/icon.png     256px runtime icon (window + About dialog)

Re-run after replacing icon-source.jpg. Requires Pillow (build-time only,
not a runtime dependency of the app).
"""

import os
from collections import deque

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP_ID = "io.github.flatpak-batch-installer"

SOURCE = os.path.join(HERE, "icon-source.jpg")
MASTER = os.path.join(HERE, "icon.png")
BANNER = os.path.join(HERE, "banner.png")
RUNTIME = os.path.join(ROOT, "flatpak_batch_installer", "data", "icon.png")
HICOLOR_SIZES = (512, 256, 128, 64, 48, 32, 16)

BG_THRESHOLD = 195   # min(R,G,B) above this counts as checkerboard background
HALO_THRESHOLD = 225  # ...and this for the 1px JPEG halo around the artwork


def key_out_background(img):
    """Return RGBA copy with the checkerboard background made transparent."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    # mask[y][x] True where the pixel looks like background
    mask = bytearray(w * h)
    for y in range(h):
        base = y * w
        for x in range(w):
            r, g, b = px[x, y]
            if min(r, g, b) > BG_THRESHOLD:
                mask[base + x] = 1
    # flood fill from every background-like border pixel
    filled = bytearray(w * h)
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if mask[y * w + x]:
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if mask[y * w + x]:
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        idx = y * w + x
        if filled[idx] or not mask[idx]:
            continue
        filled[idx] = 1
        if x > 0:
            queue.append((x - 1, y))
        if x < w - 1:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y < h - 1:
            queue.append((x, y + 1))
    # one halo pass: very-light pixels touching transparency go too
    changed = True
    halo = bytearray(filled)
    while changed:
        changed = False
        for y in range(h):
            for x in range(w):
                idx = y * w + x
                if halo[idx] or not mask[idx]:
                    continue
                r, g, b = px[x, y]
                if min(r, g, b) < HALO_THRESHOLD:
                    continue
                neighbours = (
                    (x > 0 and halo[idx - 1])
                    or (x < w - 1 and halo[idx + 1])
                    or (y > 0 and halo[idx - w])
                    or (y < h - 1 and halo[idx + w])
                )
                if neighbours:
                    halo[idx] = 1
                    changed = True
    out = rgb.convert("RGBA")
    alpha = out.load()
    removed = 0
    for y in range(h):
        for x in range(w):
            if halo[y * w + x]:
                r, g, b, _a = alpha[x, y]
                alpha[x, y] = (r, g, b, 0)
                removed += 1
    print(f"background removed: {removed} px ({100.0 * removed / (w * h):.1f}%)")
    return out


def make_banner(icon, path):
    W, H = 1600, 500
    top = (18, 32, 62)
    bottom = (10, 18, 38)
    banner = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(banner)
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    mark = icon.resize((360, 360), Image.LANCZOS)
    banner.paste(mark, (70, 70), mark)
    title = "Flatpak Batch Installer"
    subtitle = "Browse Flathub. Select many. Install once."
    max_w = W - 480 - 60
    size = 84
    while size > 20:
        font_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        left, _top, right, _bottom = draw.textbbox((0, 0), title, font=font_title)
        if right - left <= max_w:
            break
        size -= 4
    font_sub = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
    draw.text((480, 140), title, font=font_title, fill=(240, 244, 250))
    draw.text((482, 270), subtitle, font=font_sub, fill=(150, 175, 205))
    banner.save(path)
    print(f"wrote {path} (title size {size})")


def main():
    img = Image.open(SOURCE)
    print(f"source: {SOURCE} {img.size} {img.mode}")
    master = key_out_background(img)
    master.save(MASTER)
    print(f"wrote {MASTER}")
    for size in HICOLOR_SIZES:
        d = os.path.join(HERE, "hicolor", f"{size}x{size}", "apps")
        os.makedirs(d, exist_ok=True)
        small = master.resize((size, size), Image.LANCZOS)
        small.save(os.path.join(d, f"{APP_ID}.png"))
    print(f"wrote hicolor sizes {HICOLOR_SIZES}")
    os.makedirs(os.path.dirname(RUNTIME), exist_ok=True)
    master.resize((256, 256), Image.LANCZOS).save(RUNTIME)
    print(f"wrote {RUNTIME}")
    make_banner(master, BANNER)


if __name__ == "__main__":
    main()
