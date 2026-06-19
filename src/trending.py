"""Top trending AI GitHub repos this week (keyless).

Primary: scrape github.com/trending?since=weekly — GitHub's own star-velocity
list ("N stars this week") — and keep the AI-relevant rows. Fallback: the
GitHub Search API for top-starred AI repos created in the last 7 days.
Pure stdlib urllib, one request, best-effort (returns [] on failure).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.parse
import urllib.request

_AI = re.compile(
    r"\b(ai|a\.?i\.?|llm|llms|gpt|agent|agents|agentic|ml|rag|genai|generative|"
    r"neural|diffusion|transformer|transformers|prompt|prompts|chatbot|mcp|"
    r"deep[ -]?learning|machine[ -]?learning|model|models|inference|embedding)\b",
    re.I,
)


def _get(url: str, ua: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _scrape_trending(limit: int) -> list[dict]:
    html = _get("https://github.com/trending?since=weekly", "Mozilla/5.0 last30days-dashboard")
    out: list[dict] = []
    for art in html.split('class="Box-row"')[1:]:
        m = re.search(r'<h2 class="[^"]*lh-condensed[^"]*">\s*<a[^>]*href="/([^"?]+)"', art)
        if not m:
            continue
        name = m.group(1)
        pm = re.search(r"<p[^>]*>\s*(.*?)\s*</p>", art, re.S)
        desc = re.sub(r"<[^>]+>", "", pm.group(1)).strip() if pm else ""
        if not (_AI.search(name) or _AI.search(desc)):
            continue
        sm = re.search(r"([\d,]+)\s*stars this week", art)
        stars = int(sm.group(1).replace(",", "")) if sm else 0
        lm = re.search(r'itemprop="programmingLanguage">([^<]+)<', art)
        out.append({"name": name, "stars": stars, "stars_label": "this week",
                    "desc": desc[:140], "url": f"https://github.com/{name}",
                    "lang": (lm.group(1).strip() if lm else "")})
        if len(out) >= limit:
            break
    return out


def _search_api(days: int, limit: int) -> list[dict]:
    since = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    q = urllib.parse.quote(f"topic:ai created:>{since}")
    data = json.loads(_get(
        f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}",
        "last30days-dashboard"))
    return [{"name": it.get("full_name", ""), "stars": it.get("stargazers_count", 0),
             "stars_label": "total", "desc": (it.get("description") or "")[:140],
             "url": it.get("html_url", ""), "lang": it.get("language") or ""}
            for it in (data.get("items") or [])[:limit]]


def fetch_trending(days: int = 7, limit: int = 10) -> list[dict]:
    try:
        rows = _scrape_trending(limit)
        if rows:
            return rows
    except Exception:  # noqa: BLE001
        pass
    try:
        return _search_api(days, limit)
    except Exception:  # noqa: BLE001
        return []
