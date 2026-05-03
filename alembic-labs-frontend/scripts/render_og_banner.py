"""Generate the Open Graph banner for alembic.bio.

Layout (1200×630 — Telegram / X / FB summary_large_image):

    [4px red bar][         left text column         ][   alchemical seal   ]
                  performance               (white)
                  peptides, distilled.      (peptides=red, rest=white)
                  alembic.bio               (small, muted, mono)

Run:
    python scripts/render_og_banner.py
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]  # alembic-labs-frontend/
SEAL_SRC = Path(
    "/Users/macbookpro/.cursor/projects/Users-macbookpro-Downloads-alembic/"
    "assets/Gemini_Generated_Image_t1ip5lt1ip5lt1ip-0bd22066-952b-419f-867c-"
    "75c229f03596.png"
)
OUT = ROOT / "public" / "og-banner.png"

W, H = 1200, 630
BG = (0, 0, 0)
WHITE = (245, 245, 245)
RED = (255, 56, 76)         # plasma red, matches site --brand
MUTED = (140, 140, 144)
LEFT_PAD = 72
ACCENT_X = 22               # x-position of vertical red bar
ACCENT_W = 4

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_MONO = "/System/Library/Fonts/Supplemental/Andale Mono.ttf"


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def text_w(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont) -> int:
    l, _, r, _ = draw.textbbox((0, 0), s, font=font)
    return r - l


def main() -> None:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle([ACCENT_X, 0, ACCENT_X + ACCENT_W, H], fill=RED)

    seal = Image.open(SEAL_SRC).convert("RGBA")
    seal_target_w = 470
    ratio = seal_target_w / seal.width
    seal_target_h = int(seal.height * ratio)
    seal = seal.resize((seal_target_w, seal_target_h), Image.LANCZOS)
    seal_x = W - seal_target_w - 50
    seal_y = (H - seal_target_h) // 2
    canvas.paste(seal, (seal_x, seal_y), seal)

    f_big = load_font(FONT_BOLD, 92)

    line_white_top = "performance"
    line_red = "peptides,"
    line_white_bottom = "distilled."

    line_h = 104
    text_block_h = 3 * line_h
    block_top = (H - text_block_h) // 2 - 4

    draw.text((LEFT_PAD, block_top), line_white_top, font=f_big, fill=WHITE)
    draw.text((LEFT_PAD, block_top + line_h), line_red, font=f_big, fill=RED)
    draw.text(
        (LEFT_PAD, block_top + 2 * line_h), line_white_bottom, font=f_big, fill=WHITE
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    main()
