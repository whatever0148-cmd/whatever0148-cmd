"""Build the static cards: about.svg, stack.svg, projects.svg, about_page.svg."""
from __future__ import annotations

import json
import textwrap

from svgkit import (CYAN, DIM, EDGE, EDGE_HI, EMERALD, MINT, MUTED, PANEL, PANEL_HI, ROOT, TEXT,
                    document, esc, frame, write)

W = 960


def about() -> str:
    h = 176
    lines = textwrap.wrap("Building bare-metal Apple Silicon, Neural Engine compute graphs, and "
                          "zero-copy hypervisor/filesystem runtimes with Kael.", 72)
    body = frame(W, h, "kael@silicon: ~/about.md")
    body += (f'<rect x="26" y="62" width="3" height="{30 + 26 * len(lines)}" rx="1.5" fill="url(#bar)"/>'
             '<defs><linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{EMERALD}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>')
    body += (f'<g class="in" style="animation-delay:.1s"><text x="46" y="84" font-size="24" font-weight="700" fill="{TEXT}">'
             f'Systems <tspan fill="{EMERALD}">&amp;</tspan> Silicon Engineer</text></g>')
    for i, ln in enumerate(lines):
        body += (f'<g class="in" style="animation-delay:{0.35 + i * 0.2:.2f}s">'
                 f'<text x="46" y="{118 + i * 26}" font-size="15" fill="{MUTED}">{esc(ln)}</text></g>')
    css = (".in{opacity:0;animation:in .7s cubic-bezier(.2,.7,.2,1) forwards}"
           "@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}")
    return document(W, h, body, css, "About Ahmed")


def stack() -> str:
    items = ["rust", "c / arm64", "swift", "coreml mil (fp16 ane)", "apfs / xnu",
             "python", "cedar policy", "tokio", "linux"]
    fs, cw, pad, gap = 12.5, 7.5, 30, 10
    widths = [len(t) * cw + pad for t in items]
    total = sum(widths) + gap * (len(items) - 1)
    h = 108
    x = (W - total) / 2
    body = frame(W, h, "kael@silicon: ~/stack --list")
    for i, (t, w) in enumerate(zip(items, widths)):
        dot = EMERALD if i % 2 == 0 else CYAN
        body += (
            f'<g class="pill" style="animation-delay:{0.08 * i:.2f}s">'
            f'<rect x="{x:.1f}" y="56" width="{w:.1f}" height="30" rx="15" fill="{PANEL}" stroke="{EDGE_HI}"/>'
            f'<circle cx="{x + 14:.1f}" cy="71" r="3" fill="{dot}"/>'
            f'<text x="{x + 23:.1f}" y="75.5" font-size="{fs}" fill="{TEXT}">{esc(t)}</text></g>')
        x += w + gap
    css = (".pill{opacity:0;animation:pop .5s cubic-bezier(.2,.8,.2,1) forwards}"
           "@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}")
    return document(W, h, body, css, "Stack")


def projects() -> str:
    data = json.loads((ROOT / "data" / "projects.json").read_text())["projects"]
    cw_, gap, top = (W - 26 * 2 - 18) / 2, 18, 56
    card_h = 352
    h = top + card_h + 26
    body = frame(W, h, "kael@silicon: ~/projects --status")
    for i, p in enumerate(data):
        x = 26 + i * (cw_ + gap)
        live = EMERALD if p["live"] else CYAN
        g = [f'<g class="card" style="animation-delay:{0.15 + i * 0.2:.2f}s">',
             f'<rect x="{x:.1f}" y="{top}" width="{cw_:.1f}" height="{card_h}" rx="12" fill="{PANEL}" stroke="{EDGE}"/>',
             f'<rect x="{x:.1f}" y="{top}" width="{cw_:.1f}" height="3" rx="1.5" fill="{live}" opacity=".7"/>',
             # pulsing status dot
             f'<circle cx="{x + 24:.1f}" cy="{top + 34}" r="5" fill="{live}"/>',
             f'<circle cx="{x + 24:.1f}" cy="{top + 34}" r="5" fill="none" stroke="{live}">'
             f'<animate attributeName="r" values="5;13" dur="2.2s" begin="{i * 0.6:.1f}s" repeatCount="indefinite"/>'
             f'<animate attributeName="opacity" values=".9;0" dur="2.2s" begin="{i * 0.6:.1f}s" repeatCount="indefinite"/></circle>',
             f'<text x="{x + 40:.1f}" y="{top + 41}" font-size="21" font-weight="700" fill="{TEXT}">{esc(p["name"])}</text>',
             f'<text x="{x + cw_ - 18:.1f}" y="{top + 39}" font-size="11" fill="{live}" text-anchor="end">{esc(p["status"])}</text>',
             f'<text x="{x + 20:.1f}" y="{top + 66}" font-size="11.5" fill="{DIM}">{esc(p["tags"])}</text>']
        for j, ln in enumerate(textwrap.wrap(p["summary"], 54)):
            g.append(f'<text x="{x + 20:.1f}" y="{top + 96 + j * 20}" font-size="13" fill="{MUTED}">{esc(ln)}</text>')
        my = top + 164
        g.append(f'<line x1="{x + 20:.1f}" y1="{my - 8}" x2="{x + cw_ - 20:.1f}" y2="{my - 8}" stroke="{EDGE}"/>')
        for k, (val, label) in enumerate(p["metrics"]):
            yy = my + 22 + k * 42
            g.append(
                f'<g class="metric" style="animation-delay:{0.6 + i * 0.2 + k * 0.12:.2f}s">'
                f'<rect x="{x + 20:.1f}" y="{yy - 18}" width="{cw_ - 40:.1f}" height="34" rx="7" fill="{PANEL_HI}"/>'
                f'<text x="{x + 32:.1f}" y="{yy + 4}" font-size="15" font-weight="700" fill="{MINT}">{esc(val)}</text>'
                f'<text x="{x + 142:.1f}" y="{yy + 3.5}" font-size="12" fill="{MUTED}">{esc(label)}</text></g>')
        g.append("</g>")
        body += "".join(g)
    css = (".card{opacity:0;animation:rise .7s cubic-bezier(.2,.8,.2,1) forwards}"
           ".metric{opacity:0;animation:fade .5s ease-out forwards}"
           "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
           "@keyframes fade{to{opacity:1}}")
    return document(W, h, body, css, "Projects: AegisFlow and SonarANE")


def colophon() -> str:
    h = 214
    body = frame(W, h, "kael@silicon: ~/colophon")
    body += (f'<text x="26" y="72" font-size="15" font-weight="700" fill="{TEXT}">Every graphic on this page is generated in this repo.</text>'
             f'<text x="26" y="96" font-size="12.5" fill="{MUTED}">Python writes pure SMIL/CSS SVG with JetBrains Mono embedded. '
             'No external image servers, no third-party</text>'
             f'<text x="26" y="116" font-size="12.5" fill="{MUTED}">stat cards, no rate limits. A daily Actions run pulls GraphQL and commits the result.</text>')
    stages = ["graphql", "python", "smil svg", "git commit", "profile"]
    sw, sg, sy = 150, 34, 150
    x0 = (W - (len(stages) * sw + (len(stages) - 1) * sg)) / 2
    for i, s in enumerate(stages):
        x = x0 + i * (sw + sg)
        hl = EMERALD if i in (0, len(stages) - 1) else EDGE_HI
        body += (f'<rect x="{x:.1f}" y="{sy - 18}" width="{sw}" height="34" rx="8" fill="{PANEL}" stroke="{hl}"/>'
                 f'<text x="{x + sw / 2:.1f}" y="{sy + 4}" font-size="12.5" fill="{TEXT}" text-anchor="middle">{s}</text>')
        if i:
            ax = x - sg
            body += (f'<line x1="{ax + 4:.1f}" y1="{sy - 1}" x2="{x - 6:.1f}" y2="{sy - 1}" stroke="{CYAN}" '
                     f'stroke-width="1.5" stroke-dasharray="3 4"><animate attributeName="stroke-dashoffset" '
                     f'from="14" to="0" dur="0.9s" repeatCount="indefinite"/></line>'
                     f'<path d="M{x - 8:.1f},{sy - 5}l5,4l-5,4" fill="none" stroke="{CYAN}" stroke-width="1.5"/>')
    body += (f'<circle r="3.5" fill="{MINT}"><animateMotion dur="4s" repeatCount="indefinite" '
             f'path="M{x0 + sw / 2:.1f},{sy - 1}H{x0 + 4 * (sw + sg) + sw / 2:.1f}"/>'
             '<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.1;.9;1" dur="4s" repeatCount="indefinite"/></circle>')
    body += (f'<text x="{W - 26}" y="{h - 16}" font-size="10.5" fill="{DIM}" text-anchor="end">'
             'built with Kael · scripts/ · .github/workflows/sync-profile.yml</text>')
    return document(W, h, body, title="Colophon: how this profile is built")


if __name__ == "__main__":
    write("about.svg", about())
    write("stack.svg", stack())
    write("projects.svg", projects())
    write("about_page.svg", colophon())
