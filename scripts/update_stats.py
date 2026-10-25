"""Refresh data/github.json and build assets/stats_heatmap.svg.

Streaks, a 52-week contribution heatmap, and language bars (by bytes and by
repository count). Run daily by .github/workflows/sync-profile.yml.
"""
from __future__ import annotations

import datetime as dt

import ghdata
from svgkit import (CYAN, DIM, EDGE, EMERALD, MINT, MUTED, PANEL, PANEL_HI, TEXT,
                    document, esc, frame, owner, write)

W = 960
CELL, GAP = 12, 3
SHADES = [(EMERALD, .28), (EMERALD, .5), (EMERALD, .75), (EMERALD, 1), (CYAN, 1)]
BAR_COLORS = [EMERALD, CYAN, MINT, "#2dd4bf", "#38bdf8", "#86efac"]


def level(c: int, peak: int) -> int:
    if c <= 0:
        return 0
    return 1 + min(int((c / max(peak, 1)) * 4.999), 4)


def stat_cards(s: dict, y: int) -> str:
    cards = [("CURRENT STREAK", f'{s["current_streak"]}d'), ("LONGEST STREAK", f'{s["longest_streak"]}d'),
             ("CONTRIBUTIONS · 365D", s["total_year"]), ("ACTIVE DAYS", s["active_days"])]
    cw, gap = (W - 52 - 3 * 14) / 4, 14
    out = []
    for i, (k, v) in enumerate(cards):
        x = 26 + i * (cw + gap)
        out.append(f'<g class="up" style="animation-delay:{i * 0.1:.1f}s">'
                   f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="64" rx="10" fill="{PANEL}" stroke="{EDGE}"/>'
                   f'<text x="{x + 16:.1f}" y="{y + 24}" font-size="10.5" fill="{MUTED}" letter-spacing=".08em">{k}</text>'
                   f'<text x="{x + 16:.1f}" y="{y + 52}" font-size="24" font-weight="700" fill="{TEXT}">{v}</text></g>')
    return "".join(out)


def heatmap(s: dict, y: int) -> tuple[str, str]:
    grid = s["grid"]
    peak = max((c for col in grid for cell in col if cell for c in [cell[1]]), default=0)
    gw = len(grid) * (CELL + GAP) - GAP
    x0 = 62
    out, css = [], []
    month = None
    for w, col in enumerate(grid):
        x = x0 + w * (CELL + GAP)
        first = next((c for c in col if c), None)
        if first:
            m = dt.date.fromisoformat(first[0]).strftime("%b").lower()
            if m != month and dt.date.fromisoformat(first[0]).day <= 7:
                out.append(f'<text x="{x}" y="{y - 8}" font-size="10" fill="{DIM}">{m}</text>')
            month = m
        for d, cell in enumerate(col):
            if not cell:
                continue
            lv = level(cell[1], peak)
            fill, op = (PANEL_HI, 1) if lv == 0 else SHADES[lv - 1]
            cls = f"c w{w}" + (" hot" if lv else "")
            out.append(f'<rect class="{cls}" x="{x}" y="{y + d * (CELL + GAP)}" width="{CELL}" height="{CELL}" rx="2.5" '
                       f'fill="{fill}" fill-opacity="{op}"><title>{cell[0]}: {cell[1]}</title></rect>')
        css.append(f".w{w}{{animation-delay:{w * 0.018:.3f}s}}")
    for d, name in ((1, "mon"), (3, "wed"), (5, "fri")):
        out.append(f'<text x="26" y="{y + d * (CELL + GAP) + 10}" font-size="10" fill="{DIM}">{name}</text>')
    gh = 7 * (CELL + GAP) - GAP
    # a soft scan column that sweeps the year once the cells have landed
    out.append(f'<rect x="{x0 - 6}" y="{y - 4}" width="16" height="{gh + 8}" rx="4" fill="{CYAN}" opacity="0">'
               f'<animate attributeName="x" from="{x0 - 16}" to="{x0 + gw}" begin="1.4s" dur="4.5s" repeatCount="indefinite"/>'
               f'<animate attributeName="opacity" values="0;.12;.12;0" keyTimes="0;.1;.9;1" begin="1.4s" dur="4.5s" repeatCount="indefinite"/></rect>')
    legend_x = W - 26 - 5 * 15 - 70
    out.append(f'<text x="{legend_x - 8}" y="{y + gh + 22}" font-size="10" fill="{DIM}" text-anchor="end">less</text>')
    for i in range(5):
        fill, op = (PANEL_HI, 1) if i == 0 else SHADES[i]
        out.append(f'<rect x="{legend_x + i * 15}" y="{y + gh + 13}" width="11" height="11" rx="2.5" fill="{fill}" fill-opacity="{op}"/>')
    out.append(f'<text x="{legend_x + 5 * 15 + 4}" y="{y + gh + 22}" font-size="10" fill="{DIM}">more</text>')
    out.append(f'<text x="26" y="{y + gh + 22}" font-size="10" fill="{DIM}">52 weeks to {s["end"]} · peak day {s["best_day"]}</text>')
    return "".join(out), "".join(css)


def bars(title: str, rows: list[tuple[str, int]], x: float, y: int, w: float, unit) -> str:
    total = sum(v for _, v in rows) or 1
    out = [f'<text x="{x}" y="{y}" font-size="10.5" fill="{MUTED}" letter-spacing=".08em">{title}</text>']
    # stacked overview bar, then one row per language
    cx = x
    for i, (name, v) in enumerate(rows[:6]):
        seg = w * v / total
        out.append(f'<rect x="{cx:.1f}" y="{y + 12}" width="{max(seg - 2, 1):.1f}" height="8" rx="2" fill="{BAR_COLORS[i % 6]}">'
                   f'<animate attributeName="width" from="0" to="{max(seg - 2, 1):.1f}" begin="{0.5 + i * 0.08:.2f}s" dur=".8s" '
                   f'fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>')
        cx += seg
    for i, (name, v) in enumerate(rows[:6]):
        yy = y + 44 + i * 22
        pct = 100 * v / total
        out.append(f'<circle cx="{x + 5}" cy="{yy - 4}" r="4" fill="{BAR_COLORS[i % 6]}"/>'
                   f'<text x="{x + 16}" y="{yy}" font-size="12.5" fill="{TEXT}">{esc(name.lower())}</text>'
                   f'<text x="{x + w}" y="{yy}" font-size="12" fill="{MUTED}" text-anchor="end">{unit(v)} · {pct:.1f}%</text>')
    if not rows:
        out.append(f'<text x="{x}" y="{y + 44}" font-size="12" fill="{DIM}">no public repositories yet</text>')
    return "".join(out)


def kb(v: int) -> str:
    return f"{v / 1024:.1f} KB" if v < 1024 ** 2 else f"{v / 1024 ** 2:.2f} MB"


def build(s: dict) -> str:
    gy = 160
    hm, hm_css = heatmap(s, gy)
    by = gy + 7 * (CELL + GAP) + 64
    n = max(len(s["lang_bytes"][:6]), len(s["lang_repos"][:6]), 1)
    h = by + 44 + n * 22 + 10
    colw = (W - 52 - 40) / 2
    body = (frame(W, h, f"kael@silicon: ~/stats --owner {s['owner']}", f"synced {s['fetched']}")
            + stat_cards(s, 56) + hm
            + bars("LANGUAGES · BY BYTES", s["lang_bytes"], 26, by, colw, kb)
            + bars("LANGUAGES · BY REPO COUNT", s["lang_repos"], 26 + colw + 40, by, colw,
                   lambda v: f"{v} repo{'s' if v != 1 else ''}"))
    css = (".up{opacity:0;animation:up .6s cubic-bezier(.2,.8,.2,1) forwards}"
           "@keyframes up{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
           ".c{opacity:0;animation:cell .35s ease-out forwards}@keyframes cell{to{opacity:1}}"
           ".hot{animation:cell .35s ease-out forwards,glow 3.2s ease-in-out 2s infinite}"
           "@keyframes glow{0%,100%{opacity:1}50%{opacity:.72}}" + hm_css)
    return document(W, h, body, css, f"GitHub stats for {s['owner']}")


if __name__ == "__main__":
    login = owner()
    stats = ghdata.summarize(ghdata.load(login, refresh=True))
    write("stats_heatmap.svg", build(stats))
