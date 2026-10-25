"""Shared palette, font embedding and SVG helpers for every profile asset.

Every SVG in assets/ is self-contained: the JetBrains Mono glyphs it uses are
subset from fonts/ and inlined as a base64 WOFF2 @font-face, so nothing is
fetched when GitHub renders the README.
"""
from __future__ import annotations

import base64
import io
import os
import re
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ROOT / "fonts"

# one palette for the whole profile
BG = "#0d1117"
PANEL = "#0f1722"
PANEL_HI = "#131d2a"
EDGE = "#1f2a37"
EDGE_HI = "#2b3a4c"
TEXT = "#e6edf3"
MUTED = "#8b98a8"
DIM = "#4b5868"
EMERALD = "#34d399"
EMERALD_DEEP = "#10b981"
CYAN = "#22d3ee"
CYAN_SOFT = "#67e8f9"
MINT = "#a7f3d0"

FONT_STACK = "'JBM', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

_WEIGHTS = {400: "JetBrainsMono-Regular.ttf", 700: "JetBrainsMono-Bold.ttf"}


def esc(s: str) -> str:
    return escape(str(s), quote=True)


def _subset_woff2(path: Path, text: str) -> str:
    font = TTFont(path)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []  # no code ligatures: every glyph keeps its own cell
    opts.name_IDs = []
    opts.hinting = False
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    chars = {ord(c) for c in text if ord(c) >= 32} | {0x20}
    sub.populate(unicodes=chars)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def visible_text(svg_body: str) -> str:
    """Characters that can actually be drawn: text nodes, entities decoded."""
    from html import unescape
    no_style = re.sub(r"<style.*?</style>", "", svg_body, flags=re.S)
    return unescape("".join(re.findall(r">([^<]+)<", no_style)))


def font_css(svg_body: str, weights=(400, 700)) -> str:
    text = visible_text(svg_body)
    faces = []
    for w in weights:
        b64 = _subset_woff2(FONTS / _WEIGHTS[w], text)
        faces.append(
            "@font-face{font-family:'JBM';font-weight:%d;font-style:normal;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}" % (w, b64)
        )
    return "".join(faces)


def document(width: int, height: int, body: str, css: str = "", title: str = "",
             weights=(400, 700)) -> str:
    """Wrap a body in a standalone SVG with the embedded font and base styles."""
    base = (
        f"text{{font-family:{FONT_STACK};font-variant-ligatures:none;"
        "font-feature-settings:'liga' 0,'calt' 0;}"
    )
    style = font_css(body, weights) + base + css
    t = f"<title>{esc(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
        f"{t}<style>{style}</style>{body}</svg>\n"
    )


def write(name: str, svg: str) -> Path:
    ASSETS.mkdir(exist_ok=True)
    out = ASSETS / name
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(svg.encode()) / 1024:.1f} KB)")
    return out


def owner() -> str:
    """The profile owner, so a later account rename needs no code change."""
    env = os.environ.get("GITHUB_REPOSITORY_OWNER")
    if env:
        return env
    import subprocess
    try:
        url = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=True).stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+)/", url)
        if m:
            return m.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    raise SystemExit("set GITHUB_REPOSITORY_OWNER (or add an origin remote) to name the profile owner")


def smooth_path(points: list[tuple[float, float]], tension: float = 0.5) -> str:
    """Catmull-Rom spline through points, emitted as cubic-bezier segments."""
    if len(points) < 2:
        return ""
    d = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        k = tension / 3
        c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
        c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
        # clamp handles to the segment's own y-range: no dips below a zero baseline
        lo, hi = min(p1[1], p2[1]), max(p1[1], p2[1])
        c1, c2 = (c1[0], min(max(c1[1], lo), hi)), (c2[0], min(max(c2[1], lo), hi))
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return "".join(d)


def frame(width: int, height: int, label: str, right: str = "", r: int = 14) -> str:
    """Terminal-window chrome shared by every card."""
    return (
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{r}" '
        f'fill="{BG}" stroke="{EDGE}"/>'
        f'<circle cx="22" cy="20" r="4.5" fill="{EDGE_HI}"/>'
        f'<circle cx="38" cy="20" r="4.5" fill="{EDGE_HI}"/>'
        f'<circle cx="54" cy="20" r="4.5" fill="{EDGE_HI}"/>'
        f'<text x="74" y="24" font-size="11.5" fill="{MUTED}">{esc(label)}</text>'
        + (f'<text x="{width - 20}" y="24" font-size="11" fill="{DIM}" text-anchor="end">{esc(right)}</text>'
           if right else "")
        + f'<line x1="1" y1="38.5" x2="{width - 1}" y2="38.5" stroke="{EDGE}"/>'
    )
