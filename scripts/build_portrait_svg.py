"""Build assets/hero_portrait_hud.svg: a character-grid portrait with a CRT HUD.

The photo is cut out from its white backdrop, contrast-equalised (CLAHE +
gamma), sampled onto an 85-row monospace grid and written as one <text> per
row. Each row lands as a squashed streak and stretches open into glyphs, top
to bottom, then an emerald/cyan
radar sweep idles over the frame. A telemetry strip (contributions, active
days, weekly sparkline) and a link bar sit beside and under the portrait.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import ghdata
from svgkit import (BG, CYAN, CYAN_SOFT, DIM, EDGE, EDGE_HI, EMERALD, EMERALD_DEEP, MINT, MUTED,
                    PANEL, ROOT, TEXT, document, esc, frame, owner, smooth_path, write)

PHOTO = ROOT / "source" / "headshot.jpg"
ROWS = 85
CROP = (200, 22, 844, 868)          # x0, y0, x1, y1 in the 1024px source: head and collar
FS = 7.0                            # font size == row pitch
CW = FS * 0.6                       # JetBrains Mono advance: exactly 0.6em
RAMP = " .`:-=+*cxoaO#%@"           # sparse -> dense (glyph mode)
CODE_MODE = True                    # draw the face with this script's own source code
LEVELS = 8                          # tonal classes (fill-opacity steps)
REVEAL = 2.4                        # seconds for the top-to-bottom draw

W, H = 960, 750
PX, PY = 26, 54                     # portrait origin


def clahe(img: np.ndarray, tiles: int = 8, clip: float = 3.4, bins: int = 256) -> np.ndarray:
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


def code_stream() -> str:
    """This file's own source as one continuous run of glyphs: the portrait is drawn from its generator."""
    src = Path(__file__).read_text()
    return re.sub(r"\s+", " ", src)


def portrait_grid() -> tuple[list[str], list[list[int]], int]:
    src = Image.open(PHOTO).convert("RGB").crop(CROP)
    alpha = subject_mask(src)
    lum = np.asarray(src.convert("L")).astype(float) / 255
    eq = clahe(lum)
    eq = 0.72 * eq + 0.28 * lum
    detail = Image.fromarray((eq * 255).astype(np.uint8)).filter(
        ImageFilter.UnsharpMask(radius=4, percent=140, threshold=2))
    eq = np.asarray(detail).astype(float) / 255
    eq = eq ** 0.85                                  # gamma: lift midtones for a dark canvas
    if CODE_MODE:
        # keep the planes of the face (brow, cheekbones, nose, jaw), drop skin and hair detail
        eq = np.asarray(Image.fromarray((eq * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(5))).astype(float) / 255

    w, h = src.size
    cols = round(ROWS * (w / h) / 0.6)
    small = np.asarray(Image.fromarray((eq * 255).astype(np.uint8)).resize((cols, ROWS), Image.BOX)) / 255
    a_small = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((cols, ROWS), Image.BOX)) / 255

    # light falls off away from the face so the white shirt can't outshine it
    yy, xx = np.mgrid[0:ROWS, 0:cols]
    d = np.hypot((xx / cols - 0.5) / 0.5, (yy / ROWS - 0.40) / 0.55)
    small = small * (1 - 0.55 * np.clip(d - 0.3, 0, 1))
    lo, hi = np.percentile(small[a_small > 0.5], [3, 99.3])
    norm = np.clip((small - lo) / (hi - lo), 0, 1)
    # glyph mode keeps a floor for hair texture; code mode wants deep shadows so light sculpts the face
    v = norm ** 1.35 if CODE_MODE else 0.16 + 0.84 * norm ** 1.25

    # the figure dissolves into the dark instead of ending on a hard cut-out:
    # a soft edge from the mask, a fade below the collar, and seeded noise
    # so sparse glyphs scatter out at the boundary
    fade = 1 - np.clip((yy / ROWS - 0.64) / 0.26, 0, 1) ** 1.2
    weight = np.clip((a_small - 0.15) / 0.6, 0, 1) * fade
    thresh = np.random.default_rng(7).uniform(0.05, 0.95, (ROWS, cols))  # fixed seed: stable commits
    stream = code_stream() if CODE_MODE else None
    pos = 0
    chars, levels = [], []
    for r in range(ROWS):
        row_c, row_l = [], []
        for c in range(cols):
            wgt = weight[r, c]
            if wgt <= thresh[r, c]:
                row_c.append(" ")
                row_l.append(0)
                continue
            x = v[r, c] * (0.45 + 0.55 * wgt)
            if CODE_MODE:
                x = max(x, 0.02)              # shadowed code stays faintly present: the silhouette holds
            if CODE_MODE:
                # code keeps flowing left to right; brightness only sets its opacity class
                row_c.append(stream[(r * cols + c) % len(stream)])
            else:
                row_c.append(RAMP[1 + min(int(x * (len(RAMP) - 1)), len(RAMP) - 2)])
            row_l.append(1 + min(int(x * LEVELS), LEVELS - 1))
        chars.append("".join(row_c))
        levels.append(row_l)
    return chars, levels, cols


def portrait_rows(chars: list[str], levels: list[list[int]], cols: int) -> str:
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
        begin = 0.15 + r * REVEAL / ROWS
        y = PY + (r + 1) * FS
        # the row arrives squashed flat into a bright streak, then stretches open into glyphs
        out.append(
            f'<g transform="translate({PX},{y:.1f})"><text textLength="{width:.1f}" lengthAdjust="spacing" '
            f'xml:space="preserve" opacity="0">{"".join(spans)}'
            f'<set attributeName="opacity" to="1" begin="{begin:.3f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="scale" values="1.06 0.08;1.02 0.35;1 1" '
            f'keyTimes="0;0.45;1" begin="{begin:.3f}s" dur="0.6s" fill="freeze" calcMode="spline" '
            f'keySplines=".3 0 .7 1;.2 .8 .2 1"/></text></g>'
        )
    return "".join(out)


def telemetry(s: dict, x: float, y: float, w: float) -> str:
    total, active = s["total_year"], s["active_days"]
    weekly = s["weekly"]
    t0 = REVEAL + 0.3
    out = [f'<text x="{x}" y="{y}" class="k">TELEMETRY · last 365 days · github {s["source"]}</text>']
    boxes = [("CONTRIBUTIONS", total), ("ACTIVE DAYS", active), ("REPOS", s["repo_count"])]
    bw = (w - 2 * 12) / 3
    for i, (label, val) in enumerate(boxes):
        bx = x + i * (bw + 12)
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{t0 + i * 0.15:.2f}s" dur="0.4s" fill="freeze"/>'
            f'<rect x="{bx}" y="{y + 12}" width="{bw:.1f}" height="58" rx="8" fill="{PANEL}" stroke="{EDGE}"/>'
            f'<text x="{bx + 14}" y="{y + 32}" class="k">{label}</text>'
            f'<text x="{bx + 14}" y="{y + 58}" class="big">{val}</text></g>'
        )
    # weekly sparkline, Catmull-Rom smoothed into cubic beziers
    sy, sh = y + 90, 112
    peak = max(max(weekly), 1)
    pts = [(x + i * w / (len(weekly) - 1), sy + sh - 6 - (c / peak) * (sh - 14)) for i, c in enumerate(weekly)]
    line = smooth_path(pts)
    area = line + f"L{x + w:.1f},{sy + sh:.1f}L{x:.1f},{sy + sh:.1f}Z"
    lx, ly = pts[-1]
    out.append(
        f'<rect x="{x}" y="{sy}" width="{w}" height="{sh}" rx="8" fill="{PANEL}" stroke="{EDGE}"/>'
        f'<g clip-path="url(#sparkclip)">'
        f'<path d="{area}" fill="url(#sparkfill)" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{t0 + 0.9:.2f}s" dur="0.8s" fill="freeze"/></path>'
        f'<path d="{line}" fill="none" stroke="url(#sparkline)" stroke-width="1.8" stroke-linecap="round" '
        f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1">'
        f'<animate attributeName="stroke-dashoffset" from="1" to="0" begin="{t0 + 0.4:.2f}s" dur="1.6s" '
        f'fill="freeze" calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1"/></path></g>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{CYAN}" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{t0 + 2.0:.2f}s" dur="0.3s" fill="freeze"/></circle>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="none" stroke="{CYAN}" opacity="0">'
        f'<animate attributeName="r" values="3;11" dur="1.8s" begin="{t0 + 2.0:.2f}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0.8;0" dur="1.8s" begin="{t0 + 2.0:.2f}s" repeatCount="indefinite"/></circle>'
        f'<text x="{x + 12}" y="{sy + sh + 18}" class="k">52 weeks · peak {max(weekly)}/wk · synced {s["fetched"]}</text>'
    )
    return "".join(out)


def build() -> str:
    login = owner()
    stats = ghdata.summarize(ghdata.load(login, refresh="--refresh" in sys.argv))
    chars, levels, cols = portrait_grid()
    pw, ph = cols * CW, ROWS * FS
    cx, cy = PX + pw / 2, PY + ph / 2
    rx = PX + pw + 34                      # right column
    rw = W - rx - 26

    # code mode spreads the steps wider: dim code recedes, lit code carries the structure
    opac = ([0, 0.14, 0.22, 0.33, 0.46, 0.6, 0.76, 0.9, 1.0] if CODE_MODE
            else [0, 0.3, 0.42, 0.55, 0.67, 0.78, 0.88, 0.96, 1.0])
    level_css = "".join(
        f".l{i}{{fill:url(#{'hi' if i >= LEVELS - 1 else 'tone'});fill-opacity:{opac[i]}}}" for i in range(1, LEVELS + 1))
    css = (
        level_css
        + (".l7,.l8{font-weight:700}" if CODE_MODE else "")
        + f".p text{{font-size:{FS}px;}}"
        f".k{{font-size:10.5px;fill:{MUTED};letter-spacing:.08em}}"
        f".big{{font-size:22px;font-weight:700;fill:{TEXT}}}"
        f".v{{font-size:12.5px;fill:{TEXT}}}"
        f".m{{font-size:12.5px;fill:{MUTED}}}"
        ".fade{opacity:0;animation:fade .5s ease-out forwards}"
        "@keyframes fade{to{opacity:1}}"
        ".flick{animation:flick 7s steps(1) 3s infinite}"
        "@keyframes flick{0%,100%{opacity:1}47%{opacity:.93}48%{opacity:1}83%{opacity:.96}84%{opacity:1}}"
        ".blink{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
    )

    defs = (
        "<defs>"
        f'<linearGradient id="tone" gradientUnits="userSpaceOnUse" x1="{PX}" y1="{PY}" x2="{PX + pw}" y2="{PY + ph}">'
        f'<stop offset="0" stop-color="#8ff0c8"/><stop offset=".55" stop-color="{MINT}"/><stop offset="1" stop-color="{CYAN_SOFT}"/></linearGradient>'
        f'<linearGradient id="hi" gradientUnits="userSpaceOnUse" x1="{PX}" y1="{PY}" x2="{PX + pw}" y2="{PY + ph}">'
        f'<stop offset="0" stop-color="#f0fff8"/><stop offset="1" stop-color="#ecfeff"/></linearGradient>'
        f'<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{EMERALD}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{CYAN}" stop-opacity=".22"/></linearGradient>'
        f'<linearGradient id="sparkline" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{EMERALD}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>'
        f'<linearGradient id="sparkfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{EMERALD}" stop-opacity=".28"/><stop offset="1" stop-color="{EMERALD}" stop-opacity="0"/></linearGradient>'
        f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".22"/></pattern>'
        f'<clipPath id="pclip"><rect x="{PX - 8}" y="{PY - 6}" width="{pw + 16}" height="{ph + 14}" rx="10"/></clipPath>'
        f'<clipPath id="sparkclip"><rect x="{rx}" y="0" width="{rw}" height="{H}"/></clipPath>'
        "</defs>"
    )

    # radar sweep wedge: 40 degrees, rotating about the face once the draw completes
    R = max(pw, ph)
    import math
    a0, a1 = math.radians(-40), 0
    wedge = (f"M{cx:.1f},{cy:.1f}L{cx + R * math.cos(a0):.1f},{cy + R * math.sin(a0):.1f}"
             f"A{R},{R} 0 0 1 {cx + R:.1f},{cy:.1f}Z")
    crt = (
        f'<g clip-path="url(#pclip)">'
        f'<rect x="{PX - 8}" y="{PY - 6}" width="{pw + 16}" height="{ph + 14}" fill="#0a0f15"/>'
        + "".join(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{EMERALD}" stroke-opacity=".07"/>'
                  for r in (90, 180, 270))
        + f'<line x1="{cx:.1f}" y1="{PY}" x2="{cx:.1f}" y2="{PY + ph}" stroke="{EMERALD}" stroke-opacity=".05"/>'
        f'<line x1="{PX}" y1="{cy:.1f}" x2="{PX + pw}" y2="{cy:.1f}" stroke="{EMERALD}" stroke-opacity=".05"/>'
        f'<g class="p flick">{portrait_rows(chars, levels, cols)}</g>'
        f'<path d="{wedge}" fill="url(#sweep)" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" begin="{REVEAL + 0.2}s" dur="1s" fill="freeze"/>'
        f'<animateTransform attributeName="transform" type="rotate" from="0 {cx:.1f} {cy:.1f}" to="360 {cx:.1f} {cy:.1f}" '
        f'begin="{REVEAL + 0.2}s" dur="7s" repeatCount="indefinite"/></path>'
        # slow phosphor refresh band
        f'<rect x="{PX - 8}" y="{PY - 40}" width="{pw + 16}" height="40" fill="{CYAN}" opacity=".035">'
        f'<animate attributeName="y" from="{PY - 40}" to="{PY + ph}" begin="{REVEAL + 1}s" dur="5.5s" repeatCount="indefinite"/></rect>'
        f'<rect x="{PX - 8}" y="{PY - 6}" width="{pw + 16}" height="{ph + 14}" fill="url(#scan)"/>'
        "</g>"
    )
    # HUD corner brackets around the portrait
    bx0, by0, bx1, by1, L = PX - 8, PY - 6, PX + pw + 8, PY + ph + 8, 16
    brackets = "".join(
        f'<path d="M{x0},{y0 + dy * L}V{y0}H{x0 + dx * L}" fill="none" stroke="{EMERALD}" stroke-width="1.6"/>'
        for x0, y0, dx, dy in ((bx0, by0, 1, 1), (bx1, by0, -1, 1), (bx0, by1, 1, -1), (bx1, by1, -1, -1)))
    caption = (f"SUBJECT 01 · DRAWN WITH ITS OWN SOURCE · {ROWS} × {cols}" if CODE_MODE
               else f"SUBJECT 01 · {ROWS} ROWS × {cols} COLS · CLAHE γ0.85")
    hud_label = f'<text x="{bx0 + 4}" y="{by1 + 18}" class="k">{caption}</text>'

    # right column: identity + readout, typed in after the portrait lands
    t = REVEAL + 0.1
    ident = (
        f'<g class="fade" style="animation-delay:.4s">'
        f'<text x="{rx}" y="{PY + 18}" class="k">kael@silicon:~$ whoami</text>'
        f'<text x="{rx}" y="{PY + 62}" font-size="40" font-weight="700" fill="{TEXT}" letter-spacing="2">AHMED</text>'
        f'<text x="{rx}" y="{PY + 88}" font-size="14" fill="{EMERALD}">systems &amp; silicon engineer</text>'
        "</g>"
    )
    rows = [
        ("target", "apple m2 · 16-core neural engine"),
        ("layer", "bare metal → ane graphs → runtimes"),
        ("focus", "zero-copy hypervisor / fs paths"),
        ("partner", "kael · co-founder"),
        ("status", "● shipping"),
    ]
    readout = []
    for i, (k, v) in enumerate(rows):
        yy = PY + 128 + i * 22
        color = f' fill="{EMERALD}"' if k == "status" else ""
        readout.append(
            f'<g class="fade" style="animation-delay:{0.7 + i * 0.18:.2f}s">'
            f'<text x="{rx}" y="{yy}" class="m">{k}</text>'
            f'<text x="{rx + 78}" y="{yy}" class="v"{color}>{esc(v)}</text></g>')
    cursor = (f'<g class="fade" style="animation-delay:1.7s"><text x="{rx}" y="{PY + 128 + 5 * 22 + 4}" class="m">'
              f'kael@silicon:~$ <tspan class="blink" fill="{EMERALD}">█</tspan></text></g>')
    tele = telemetry(stats, rx, PY + ph - 232, rw)

    # link bar (the README repeats these as clickable links: <img> SVGs can't link)
    ly = H - 34
    links = [("github", f"github.com/{login}"), ("mail", "f2026376047@umt.edu.pk"),
             ("repo", "SonarANE"), ("repo", "AegisFlow")]
    seg, lx = [], 26
    for i, (k, v) in enumerate(links):
        if i:
            seg.append(f'<text x="{lx}" y="{ly + 4}" class="m">·</text>')
            lx += 22
        seg.append(f'<text x="{lx}" y="{ly + 4}" class="k">{k}</text>')
        lx += len(k) * 6.6 + 8
        seg.append(f'<text x="{lx}" y="{ly + 4}" class="v">{esc(v)}</text>')
        lx += len(v) * 7.5 + 14
    linkbar = (f'<line x1="1" y1="{ly - 20.5}" x2="{W - 1}" y2="{ly - 20.5}" stroke="{EDGE}"/>'
               f'<g class="fade" style="animation-delay:{t:.1f}s">{"".join(seg)}</g>')

    body = (defs + frame(W, H, f"kael@silicon: ~/{login} — hud", f"rev {stats['fetched']}")
            + crt + brackets + hud_label + ident + "".join(readout) + cursor + tele + linkbar)
    return document(W, H, body, css, title=f"Ahmed — systems & silicon engineer ({login})")


if __name__ == "__main__":
    write("hero_portrait_hud.svg", build())
