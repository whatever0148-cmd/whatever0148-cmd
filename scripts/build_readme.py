"""Write README.md for the current owner, so links follow an account rename."""
from __future__ import annotations

import json

from svgkit import ROOT, owner

EMAIL = "f2026376047@umt.edu.pk"


def build(login: str) -> str:
    projects = json.loads((ROOT / "data" / "projects.json").read_text())["projects"]
    public = [p["name"] for p in projects if p["live"]]
    repo_links = " · ".join(
        f'<a href="https://github.com/{login}/{n}">{n}</a>' for n in ("SonarANE", "AegisFlow") if n in public)
    links = " · ".join(filter(None, [
        f'<a href="https://github.com/{login}">github</a>',
        f'<a href="mailto:{EMAIL}">{EMAIL}</a>',
        repo_links,
    ]))
    project_img = '<img src="assets/projects.svg" width="100%" alt="AegisFlow and SonarANE project cards">'
    return f"""<div align="center">

<img src="assets/hero_portrait_hud.svg" width="100%" alt="Ahmed: character-grid portrait with live GitHub telemetry">

<sub>{links}</sub>

<img src="assets/about.svg" width="100%" alt="Systems &amp; Silicon Engineer: bare-metal Apple Silicon, Neural Engine compute graphs, zero-copy hypervisor/filesystem runtimes, with Kael">

<img src="assets/stack.svg" width="100%" alt="Stack: rust, c / arm64, swift, coreml mil (fp16 ane), apfs / xnu, python, cedar policy, tokio, linux">

{f'<a href="https://github.com/{login}/SonarANE">{project_img}</a>' if "SonarANE" in public else project_img}

<img src="assets/stats_heatmap.svg" width="100%" alt="Contribution streaks, 52-week heatmap and language breakdown">

<img src="assets/about_page.svg" width="100%" alt="Colophon: every graphic is generated in this repo as SMIL/CSS SVG">

</div>
"""


if __name__ == "__main__":
    (ROOT / "README.md").write_text(build(owner()))
    print("wrote README.md")
