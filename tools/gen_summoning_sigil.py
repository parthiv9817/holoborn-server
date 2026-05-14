"""Generate the cyan summoning sigil PNG used as the Stage 1 floor disc texture.

Output: drafts/summoning_sigil.png (1024x1024, RGBA with alpha).
Re-run after tweaking line widths, ring counts, or colors below.
"""

from PIL import Image, ImageDraw
import math
from pathlib import Path

SIZE = 1024
SCALE = 4  # supersample for clean antialiased edges
W = SIZE * SCALE

CYAN_FULL = (0, 224, 255, 255)
CYAN_STRONG = (0, 224, 255, 215)
CYAN_MED = (0, 224, 255, 155)
CYAN_FAINT = (0, 224, 255, 100)


def lw(base_px: int) -> int:
    return base_px * SCALE


def main() -> None:
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = W // 2, W // 2

    # Outer circle (faintest, largest)
    r_outer = int(W * 0.46)
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
                 outline=CYAN_FAINT, width=lw(3))

    # Second circle
    r_second = int(W * 0.36)
    draw.ellipse([cx - r_second, cy - r_second, cx + r_second, cy + r_second],
                 outline=CYAN_MED, width=lw(2))

    # Six hexagram vertices
    r_hex = int(W * 0.38)
    hex_points = []
    for i in range(6):
        angle = math.radians(60 * i - 90)
        x = cx + r_hex * math.cos(angle)
        y = cy + r_hex * math.sin(angle)
        hex_points.append((x, y))

    # Hexagon connecting all 6 vertices
    draw.polygon(hex_points, outline=CYAN_STRONG, width=lw(3))

    # Upward triangle (vertices 0, 2, 4)
    draw.polygon([hex_points[0], hex_points[2], hex_points[4]],
                 outline=CYAN_MED, width=lw(2))

    # Downward triangle (vertices 1, 3, 5)
    draw.polygon([hex_points[1], hex_points[3], hex_points[5]],
                 outline=CYAN_MED, width=lw(2))

    # Inner circle
    r_inner = int(W * 0.13)
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
                 outline=CYAN_STRONG, width=lw(2))

    # Center dot
    r_dot = int(W * 0.015)
    draw.ellipse([cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot], fill=CYAN_FULL)

    # Vertex dots at each hexagram point
    for px, py in hex_points:
        r = int(W * 0.009)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=CYAN_FULL)

    # Downscale with high-quality resampling
    final = img.resize((SIZE, SIZE), Image.LANCZOS)

    out_path = Path(__file__).resolve().parents[1] / "drafts" / "summoning_sigil.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "PNG")
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
