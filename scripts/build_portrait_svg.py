"""Build assets/hero_portrait_hud.svg: a character-ramp portrait over live telemetry.

The photo is cut out from its white backdrop, contrast-equalised (CLAHE +
gamma) and pushed through a 70-step character ramp on an 85-row monospace
grid, one <text> per row. Each row lands as a squashed horizontal streak that
stretches open into glyphs, top to bottom. Under the head: contributions in
the last year, active days, best week and a weekly sparkline, all from the
GitHub GraphQL API. Ink follows the viewer's light/dark preference.
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import ghdata
from svgkit import ROOT, document, esc, owner, smooth_path, write

PHOTO = ROOT / "source" / "headshot.jpg"
ROWS = 85
CROP = (250, 28, 800, 720)          # x0, y0, x1, y1 in the 1024px source: head to chin
FS = 5.6                            # font size == row pitch
CW = FS * 0.6                       # JetBrains Mono advance: exactly 0.6em
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
LEVELS = 8                          # tonal classes (fill-opacity steps)
OPACITY = [0, 0.18, 0.28, 0.4, 0.52, 0.65, 0.78, 0.9, 1.0]
REVEAL = 2.8                        # seconds for the top-to-bottom draw

W = 860


def clahe(img: np.ndarray, tiles: int = 8, clip: float = 2.8, bins: int = 256) -> np.ndarray:
    """Contrast-limited adaptive histogram equalisation on a [0,1] image."""
    h, w = img.shape
    th, tw = h // tiles, w // tiles
    q = np.clip((img * (bins - 1)).astype(int), 0, bins - 1)
    luts = np.zeros((tiles, tiles, bins))
    for i in range(tiles):
        for j in range(tiles):
            tile = q[i * th:(i + 1) * th, j * tw:(j + 1) * tw]
            hist = np.bincount(tile.ravel(), minlength=bins).astype(float)
            limit = clip * tile.size / bins
            excess = np.maximum(hist - limit, 0).sum()
            hist = np.minimum(hist, limit) + excess / bins
            cdf = hist.cumsum()
            luts[i, j] = (cdf - cdf[0]) / max(cdf[-1] - cdf[0], 1)
    # bilinear blend between the four nearest tile mappings
    yc = (np.arange(h) + 0.5) / th - 0.5
    xc = (np.arange(w) + 0.5) / tw - 0.5
    y0 = np.clip(np.floor(yc).astype(int), 0, tiles - 1)
    x0 = np.clip(np.floor(xc).astype(int), 0, tiles - 1)
    y1, x1 = np.clip(y0 + 1, 0, tiles - 1), np.clip(x0 + 1, 0, tiles - 1)
    fy = np.clip(yc - y0, 0, 1)[:, None]
    fx = np.clip(xc - x0, 0, 1)[None, :]
    Y0, X0, Y1, X1 = y0[:, None], x0[None, :], y1[:, None], x1[None, :]
    top = luts[Y0, X0, q] * (1 - fx) + luts[Y0, X1, q] * fx
    bot = luts[Y1, X0, q] * (1 - fx) + luts[Y1, X1, q] * fx
    return top * (1 - fy) + bot * fy


def subject_mask(rgb: Image.Image) -> np.ndarray:
    """Alpha for everything that isn't the white studio backdrop."""
    a = np.asarray(rgb).astype(float)
    cand = (a.min(2) > 214) & (np.ptp(a, axis=2) < 22)
    m = Image.fromarray(np.where(cand, 255, 0).astype(np.uint8)).copy()
    w, h = m.size
    # flood from the top and side edges only: the shirt touches the bottom edge
    seeds = [(x, 0) for x in range(0, w, 4)] + [(0, y) for y in range(0, h, 4)] + \
            [(w - 1, y) for y in range(0, h, 4)]
    for s in seeds:
        if m.getpixel(s) == 255:
            ImageDraw.floodfill(m, s, 128)
    bg = np.asarray(m) == 128
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    return np.asarray(alpha).astype(float) / 255


def portrait_grid() -> tuple[list[str], list[list[int]], int]:
    src = Image.open(PHOTO).convert("RGB").crop(CROP)
    alpha = subject_mask(src)
    lum = np.asarray(src.convert("L")).astype(float) / 255
    eq = 0.7 * clahe(lum) + 0.3 * lum
    detail = Image.fromarray((eq * 255).astype(np.uint8)).filter(
        ImageFilter.UnsharpMask(radius=3, percent=120, threshold=2))
    eq = np.asarray(detail).astype(float) / 255

    w, h = src.size
    cols = round(ROWS * (w / h) / 0.6)
    small = np.asarray(Image.fromarray((eq * 255).astype(np.uint8)).resize((cols, ROWS), Image.BOX)) / 255
    a_small = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((cols, ROWS), Image.BOX)) / 255

    lo, hi = np.percentile(small[a_small > 0.5], [2, 99.5])
    # gamma for a dark canvas; the floor keeps dark hair readable as texture
    v = 0.14 + 0.86 * np.clip((small - lo) / (hi - lo), 0, 1) ** 1.1

    # below the chin the figure frays out instead of ending on a straight cut
    yy = np.mgrid[0:ROWS, 0:cols][0]
    fade = 1 - np.clip((yy / ROWS - 0.82) / 0.18, 0, 1)
    weight = np.clip((a_small - 0.2) / 0.5, 0, 1) * fade
    noise = np.random.default_rng(7).uniform(0.05, 0.9, (ROWS, cols))  # fixed seed: stable commits
    keep = weight > np.where(yy / ROWS > 0.8, noise, 0.05)

    chars, levels = [], []
    for r in range(ROWS):
        row_c, row_l = [], []
        for c in range(cols):
            if not keep[r, c]:
                row_c.append(" ")
                row_l.append(0)
                continue
            x = v[r, c]
            row_c.append(RAMP[1 + min(int(x * (len(RAMP) - 1)), len(RAMP) - 2)])
            row_l.append(1 + min(int(x * LEVELS), LEVELS - 1))
        chars.append("".join(row_c))
        levels.append(row_l)
    return chars, levels, cols


def portrait_rows(chars: list[str], levels: list[list[int]], cols: int, px: float, py: float) -> str:
    out = []
    width = cols * CW
    for r, (line, lv) in enumerate(zip(chars, levels)):
        if not line.strip():
            continue
        spans, i = [], 0
        while i < cols:
            j = i
            while j < cols and lv[j] == lv[i]:
                j += 1
            seg = line[i:j]
            spans.append(f'<tspan class="l{lv[i]}">{esc(seg)}</tspan>' if lv[i] else esc(seg))
            i = j
        begin = 0.2 + r * REVEAL / ROWS
        y = py + (r + 1) * FS
        # the row arrives squashed flat into a bright streak, then stretches open into glyphs
        out.append(
            f'<g transform="translate({px:.1f},{y:.1f})"><text textLength="{width:.1f}" lengthAdjust="spacing" '
            f'xml:space="preserve" opacity="0">{"".join(spans)}'
            f'<set attributeName="opacity" to="1" begin="{begin:.3f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="scale" values="1.06 0.08;1.02 0.35;1 1" '
            f'keyTimes="0;0.45;1" begin="{begin:.3f}s" dur="0.6s" fill="freeze" calcMode="spline" '
            f'keySplines=".3 0 .7 1;.2 .8 .2 1"/></text></g>'
        )
    return "".join(out)


def telemetry(s: dict, x0: float, x1: float, y: float) -> str:
    t0 = REVEAL + 0.4
    w = x1 - x0
    out = [
        f'<g class="in" style="animation-delay:{t0:.1f}s">'
        f'<text x="{x0}" y="{y + 36}" font-size="40" font-weight="700" class="ink">{s["total_year"]}</text>'
        f'<text x="{x0 + 2}" y="{y + 56}" font-size="10.5" class="soft">contributions in the last year</text>'
        f'<text x="{x1}" y="{y + 12}" font-size="16" font-weight="700" class="ink" text-anchor="end">{s["active_days"]}</text>'
        f'<text x="{x1}" y="{y + 25}" font-size="9.5" class="soft" text-anchor="end">active days</text>'
        f'<text x="{x1}" y="{y + 45}" font-size="16" font-weight="700" class="ink" text-anchor="end">{s["best_week"]}</text>'
        f'<text x="{x1}" y="{y + 58}" font-size="9.5" class="soft" text-anchor="end">best week</text>'
        "</g>"
    ]
    weekly = s["weekly"]
    sy, sh = y + 72, 52
    peak = max(max(weekly), 1)
    pts = [(x0 + i * w / (len(weekly) - 1), sy + sh - 2 - (c / peak) * (sh - 8)) for i, c in enumerate(weekly)]
    line = smooth_path(pts)
    area = line + f"L{x1:.1f},{sy + sh:.1f}L{x0:.1f},{sy + sh:.1f}Z"
    lx, ly = pts[-1]
    out.append(
        f'<path d="{area}" class="area" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{t0 + 0.8:.2f}s" dur="0.8s" fill="freeze"/></path>'
        f'<path d="{line}" fill="none" class="stroke" stroke-width="1.6" stroke-linecap="round" '
        f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1">'
        f'<animate attributeName="stroke-dashoffset" from="1" to="0" begin="{t0 + 0.2:.2f}s" dur="1.6s" '
        f'fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/></path>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" class="dot" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{t0 + 1.8:.2f}s" dur="0.3s" fill="freeze"/></circle>'
    )
    return "".join(out)


def build() -> str:
    login = owner()
    stats = ghdata.summarize(ghdata.load(login, refresh="--refresh" in sys.argv))
    chars, levels, cols = portrait_grid()
    pw, ph = cols * CW, ROWS * FS
    px, py = (W - pw) / 2, 8
    ty = py + ph + 34
    h = round(ty + 136)

    css = (
        # ink follows the viewer's theme: light text on dark GitHub, dark text on light
        "svg{color:#e6edf3}@media (prefers-color-scheme:light){svg{color:#1f2328}}"
        + "".join(f".l{i}{{fill:currentColor;fill-opacity:{OPACITY[i]}}}" for i in range(1, LEVELS + 1))
        + f".p text{{font-size:{FS}px}}"
        ".ink{fill:currentColor}.soft{fill:currentColor;fill-opacity:.6}"
        ".area{fill:currentColor;fill-opacity:.22}.stroke{stroke:currentColor}.dot{fill:currentColor}"
        ".in{opacity:0;animation:in .6s ease-out forwards}@keyframes in{to{opacity:1}}"
    )
    body = (f'<g class="p">{portrait_rows(chars, levels, cols, px, py)}</g>'
            + telemetry(stats, W / 2 - 300, W / 2 + 300, ty))
    return document(W, h, body, css, title=f"Ahmed ({login}): character portrait and contribution telemetry")


if __name__ == "__main__":
    write("hero_portrait_hud.svg", build())
