#!/usr/bin/env python3
"""
Build favicons from the author's reference mercury ☿ PNG (transparent bg in tab).

1) Prefer scripts/mercury-reference.png — same silhouette & coral tones as screenshot.
2) Fallback: render ☿ via JetBrains Mono Bold (plasma red) if reference missing.

    python3 scripts/render_mercury_icons.py
"""

from __future__ import annotations

import base64
import io
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GLYPH = "\u263f"
FONT_NAME = "JetBrainsMono-Bold.ttf"
FALLBACK_RGB = (255, 51, 68)

SCRIPT_DIR = Path(__file__).resolve().parent
PUB_DIR = SCRIPT_DIR.parent / "public"
REFERENCE_PATH = SCRIPT_DIR / "mercury-reference.png"


def font_file() -> Path | None:
    path = SCRIPT_DIR / "fonts" / FONT_NAME
    return path if path.exists() else None


def upscale(im: Image.Image, min_side: int = 512) -> Image.Image:
    """Sharper masking / resize when upscaling tiny reference art."""
    w, h = im.size
    m = max(w, h)
    if m >= min_side:
        return im
    scale = min_side / m
    nw, nh = int(w * scale), int(h * scale)
    return im.resize((max(1, nw), max(1, nh)), Image.Resampling.LANCZOS)


def flood_transparent(rgb: Image.Image, thr: float = 12.5) -> Image.Image:
    """
    Flood-fill background from borders: traverse only pixels with max(rgb)<=thr.
    Preserves reddish symbol interior (won't classify (28,9,9) as wall if thr low).
    """
    w, h = rgb.size
    px = rgb.load()

    def is_wall(x: int, y: int) -> bool:
        r, g, b = px[x, y]
        return max(r, g, b) <= thr

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_px = out.load()
    visited = [[False] * h for _ in range(w)]
    dq: deque[tuple[int, int]] = deque()

    def try_push(x: int, y: int) -> None:
        if 0 <= x < w and 0 <= y < h and not visited[x][y] and is_wall(x, y):
            visited[x][y] = True
            dq.append((x, y))

    for x in range(w):
        try_push(x, 0)
        try_push(x, h - 1)
    for y in range(h):
        try_push(0, y)
        try_push(w - 1, y)

    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny] and is_wall(nx, ny):
                visited[nx][ny] = True
                dq.append((nx, ny))

    # Enclosed blacks (inside the ring ☿ hollow) don't border-fill; punch them through.
    hole_max = 18

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if visited[x][y]:
                out_px[x, y] = (0, 0, 0, 0)
            elif max(r, g, b) <= hole_max:
                out_px[x, y] = (0, 0, 0, 0)
            else:
                out_px[x, y] = (r, g, b, 255)
    return out


def trim_and_square(im: Image.Image, pad_ratio: float = 0.08) -> Image.Image:
    alpha = im.split()[3]
    bbox = alpha.getbbox()
    if not bbox:
        return im
    cropped = im.crop(bbox)
    w, h = cropped.size
    side = max(w, h)
    pad = max(2, int(side * pad_ratio))
    canvas_side = side + 2 * pad
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    ox = pad + (side - w) // 2
    oy = pad + (side - h) // 2
    canvas.paste(cropped, (ox, oy), cropped)
    return canvas


def raster_from_reference(size_px: int) -> Image.Image:
    src = Image.open(REFERENCE_PATH).convert("RGB")
    big = upscale(src, min_side=640)
    cut = flood_transparent(big, thr=12.5)
    boxed = trim_and_square(cut, pad_ratio=0.06)
    return boxed.resize((size_px, size_px), Image.Resampling.LANCZOS)


def raster_from_font(size_px: int, supersample: int = 640) -> Image.Image:
    ttf = font_file()
    if not ttf:
        raise RuntimeError("No reference and no JetBrains Mono TTF.")
    rgb = FALLBACK_RGB
    hi = Image.new("RGBA", (supersample, supersample), (0, 0, 0, 0))
    dr = ImageDraw.Draw(hi)
    fs = int(supersample * 0.78)
    font = ImageFont.truetype(str(ttf), fs)
    dr.text(
        (supersample / 2, supersample / 2),
        GLYPH,
        font=font,
        fill=rgb + (255,),
        anchor="mm",
    )
    return hi.resize((size_px, size_px), Image.Resampling.LANCZOS)


def raster_any(size_px: int) -> Image.Image:
    if REFERENCE_PATH.exists():
        try:
            return raster_from_reference(size_px)
        except OSError:
            pass
    return raster_from_font(size_px)


def svg_embed_png(png_bytes: bytes, view_len: int) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {view_len} {view_len}">'
        f'<image width="{view_len}" height="{view_len}" '
        f'href="data:image/png;base64,{b64}"/>'
        "</svg>\n"
    )


def main() -> int:
    PUB_DIR.mkdir(parents=True, exist_ok=True)

    mode = "reference" if REFERENCE_PATH.exists() else "font-fallback"
    print(f"favicon source: {mode}")

    for fname, dim in (
        ("favicon-16x16.png", 16),
        ("favicon-32x32.png", 32),
        ("favicon-48x48.png", 48),
        ("apple-touch-icon.png", 180),
    ):
        raster_any(dim).save(PUB_DIR / fname, optimize=True)

    buf32 = io.BytesIO()
    raster_any(32).save(buf32, format="PNG", optimize=True)
    (PUB_DIR / "mercury-favicon.svg").write_text(svg_embed_png(buf32.getvalue(), 32), encoding="utf-8")

    buf128 = io.BytesIO()
    raster_any(128).save(buf128, format="PNG", optimize=True)
    (PUB_DIR / "mercury-mark.svg").write_text(svg_embed_png(buf128.getvalue(), 128), encoding="utf-8")

    print("OK — wrote centred transparent favicons (+ SVG wrappers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
