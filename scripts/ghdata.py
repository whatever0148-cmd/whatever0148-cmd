"""GitHub activity for the profile owner, cached in data/github.json.

With GITHUB_TOKEN (as in the Actions workflow) everything comes from the
GraphQL API. Without one, the public contribution calendar and REST language
endpoints are used, so the generators still run on a laptop.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.request
from collections import Counter
from html import unescape

from svgkit import ROOT

CACHE = ROOT / "data" / "github.json"
UA = {"User-Agent": "profile-svg-generator"}

CAL_QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    createdAt
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

REPO_QUERY = """
query($login:String!) {
  user(login:$login) {
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC) {
      nodes { name languages(first:20, orderBy:{field:SIZE, direction:DESC}) { edges { size node { name } } } }
    }
  }
}"""


def _get(url: str, token: str | None = None, body: dict | None = None):
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
    return json.loads(raw) if url.startswith("https://api.") else raw


def _graphql(token: str, query: str, **variables):
    out = _get("https://api.github.com/graphql", token, {"query": query, "variables": variables})
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


def _days_graphql(login: str, token: str) -> dict[str, int]:
    today = dt.date.today()
    first = _graphql(token, CAL_QUERY, login=login,
                     **{"from": f"{today.year}-01-01T00:00:00Z", "to": f"{today}T23:59:59Z"})
    created = dt.date.fromisoformat(first["user"]["createdAt"][:10])
    days: dict[str, int] = {}
    # one calendar per year since the account was created (the API caps a range at a year)
    for year in range(created.year, today.year + 1):
        end = today if year == today.year else dt.date(year, 12, 31)
        res = first if year == today.year else _graphql(
            token, CAL_QUERY, login=login,
            **{"from": f"{year}-01-01T00:00:00Z", "to": f"{end}T23:59:59Z"})
        for w in res["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return days


def _days_public(login: str) -> dict[str, int]:
    """Parse github.com/users/<login>/contributions (the public profile calendar)."""
    days: dict[str, int] = {}
    today = dt.date.today()
    for year in range(today.year - 1, today.year + 1):
        html = _get(f"https://github.com/users/{login}/contributions?from={year}-01-01&to={year}-12-31")
        ids = {}
        for td in re.findall(r"<td\b[^>]*>", html):
            date, cid = re.search(r'data-date="([\d-]+)"', td), re.search(r'\bid="([^"]+)"', td)
            if date and cid:
                ids[date.group(1)] = cid.group(1)
        by_id = {}
        for target, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html):
            m = re.match(r"(\d+) contribution", unescape(label))
            by_id[target] = int(m.group(1)) if m else 0
        for date, cid in ids.items():
            if date <= today.isoformat():
                days[date] = by_id.get(cid, 0)
    return days


def _languages_graphql(login: str, token: str):
    nodes = _graphql(token, REPO_QUERY, login=login)["user"]["repositories"]["nodes"]
    return {n["name"]: {e["node"]["name"]: e["size"] for e in n["languages"]["edges"]} for n in nodes}


def _languages_public(login: str):
    repos = _get(f"https://api.github.com/users/{login}/repos?per_page=100&type=owner")
    return {r["name"]: _get(r["languages_url"]) for r in repos if not r["fork"]}


def fetch(login: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    try:
        if not token:
            raise RuntimeError("no token")
        days, langs, source = _days_graphql(login, token), _languages_graphql(login, token), "graphql"
    except Exception as exc:  # no token, or the token can't see the calendar
        print(f"graphql unavailable ({exc}); using the public calendar")
        days, langs, source = _days_public(login), _languages_public(login), "public"
    langs.pop(login, None)  # the profile repo is generator code, not project work
    data = {
        "owner": login,
        "fetched": dt.date.today().isoformat(),
        "source": source,
        "days": sorted(days.items()),
        "repo_languages": langs,
    }
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1) + "\n")
    return data


def load(login: str, refresh: bool = False) -> dict:
    """Cached data for login; refetched when asked, stale, or for another owner."""
    if not refresh and CACHE.exists():
        data = json.loads(CACHE.read_text())
        if data.get("owner") == login and data.get("fetched") == dt.date.today().isoformat():
            return data
    try:
        return fetch(login)
    except Exception as exc:  # offline: keep rendering from the last good snapshot
        if CACHE.exists():
            print(f"fetch failed ({exc}); using cached {CACHE.name}")
            return json.loads(CACHE.read_text())
        raise


def summarize(data: dict) -> dict:
    days = {dt.date.fromisoformat(d): c for d, c in data["days"]}
    end = max(days) if days else dt.date.today()
    year = [end - dt.timedelta(days=i) for i in range(364, -1, -1)]
    counts = [days.get(d, 0) for d in year]

    longest = run = 0
    longest_span = cur_start = None
    for d in sorted(days):
        if days[d] > 0:
            cur_start = d if run == 0 else cur_start
            run += 1
            if run > longest:
                longest, longest_span = run, (cur_start, d)
        else:
            run = 0
    current, cur = 0, end
    if days.get(cur, 0) == 0:  # today still open: a streak is alive if yesterday counted
        cur -= dt.timedelta(days=1)
    current_end = cur
    while days.get(cur, 0) > 0:
        current += 1
        cur -= dt.timedelta(days=1)
    current_span = (cur + dt.timedelta(days=1), current_end) if current else None

    # 53 Sunday-first columns ending at the week that contains `end`, like github.com
    start = end - dt.timedelta(days=(end.weekday() + 1) % 7) - dt.timedelta(weeks=52)
    grid = []
    for w in range(53):
        col = []
        for dow in range(7):
            d = start + dt.timedelta(weeks=w, days=dow)
            col.append(None if d > end else (d.isoformat(), days.get(d, 0)))
        grid.append(col)
    weekly = [sum(c for _, c in filter(None, col)) for col in grid]

    lang_bytes, lang_repos = Counter(), Counter()
    for repo, langs in data["repo_languages"].items():
        for name, size in langs.items():
            lang_bytes[name] += size
        if langs:
            lang_repos[max(langs, key=langs.get)] += 1

    active = [d for d in sorted(days) if days[d] > 0]
    return {
        "owner": data["owner"],
        "fetched": data["fetched"],
        "source": "graphql api" if data.get("source") == "graphql" else "public calendar",
        "end": end.isoformat(),
        "total_year": sum(counts),
        "active_days": sum(1 for c in counts if c > 0),
        "best_day": max(counts) if counts else 0,
        "current_streak": current,
        "longest_streak": longest,
        "first_active": active[0].isoformat() if active else None,
        "weekly": weekly,
        "best_week": max(weekly) if weekly else 0,
        "current_span": [d.isoformat() for d in current_span] if current_span else None,
        "longest_span": [d.isoformat() for d in longest_span] if longest_span else None,
        "grid": grid,
        "lang_bytes": lang_bytes.most_common(),
        "lang_repos": lang_repos.most_common(),
        "repo_count": len(data["repo_languages"]),
    }
