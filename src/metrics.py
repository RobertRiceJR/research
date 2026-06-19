"""KPI metrics store + executive dashboard for the daily research loop.

Persists one record per run to metrics/kpi.jsonl and renders a self-contained
dark-mode dashboard (metrics/dashboard.html) with cumulative + per-run charts.
Inline SVG only — no external chart library, no network, fully shareable.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "metrics" / "kpi.jsonl"
DASHBOARD = ROOT / "metrics" / "dashboard.html"

# Interactions = upvotes + points + reactions + comments (matches the digest's
# relevance score). Views are tracked separately as "reach" so impressions
# don't drown out genuine engagement.
_ENGAGEMENT_RE = re.compile(r"(\d[\d,]*)\s+(?:upvotes|points|reactions|comments)\b", re.IGNORECASE)
_VIEWS_RE = re.compile(r"(\d[\d,]*)\s+views\b", re.IGNORECASE)
_FOOTER_SRC_RE = re.compile(r"^[├└]─\s*\S+\s*(Reddit|YouTube|HN|GitHub|Polymarket)\s*:(.*)$", re.MULTILINE)
_SOURCE_KEY = {"Reddit": "reddit", "YouTube": "youtube", "HN": "hackernews",
               "GitHub": "github", "Polymarket": "polymarket"}


def _sum(pattern: re.Pattern, text: str) -> int:
    return sum(int(n.replace(",", "")) for n in pattern.findall(text))


# Sources reliably expected to return data on a healthy multi-topic run.
# Polymarket is excluded — it's opportunistic (most niche topics have no markets),
# so its absence is normal, not an outage.
CORE_SOURCES = ("reddit", "hackernews", "github", "youtube")


def sources_present(raw_md: str) -> set:
    """Which sources actually returned items (have a footer line) for one topic."""
    return {_SOURCE_KEY.get(src, src.lower()) for src, _ in _FOOTER_SRC_RE.findall(raw_md)}


def source_breakdown(raw_md: str) -> tuple[dict, int]:
    """Per-source interactions + YouTube reach (views) from one topic's footer."""
    inter: dict[str, int] = {}
    reach = 0
    for src, rest in _FOOTER_SRC_RE.findall(raw_md):
        key = _SOURCE_KEY.get(src, src.lower())
        inter[key] = inter.get(key, 0) + _sum(_ENGAGEMENT_RE, rest)
        if src == "YouTube":
            reach += _sum(_VIEWS_RE, rest)
    return inter, reach


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------
def load_all() -> list[dict]:
    if not STORE.exists():
        return []
    return [json.loads(ln) for ln in STORE.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _key(r: dict) -> tuple:
    return (r.get("date", ""), r.get("tag", ""))


def record(rec: dict, overwrite: bool = True) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    rows = load_all()
    if any(_key(r) == _key(rec) for r in rows):
        if not overwrite:
            return
        rows = [r for r in rows if _key(r) != _key(rec)]
    rows.append(rec)
    rows.sort(key=lambda r: (r.get("date", ""), r.get("tag", ""), r.get("ts", "")))
    STORE.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def attach_quality(date: str, tag: str, quality: dict) -> None:
    """Set the `quality` field on an existing run record (judge re-scores)."""
    rows = load_all()
    for r in rows:
        if r.get("date") == date and r.get("tag", "") == (tag or ""):
            r["quality"] = quality
    STORE.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def record_run(*, date: str, tag: str, per_topic: dict, sources: list,
               bullets: int, citations: int, source_interactions: dict | None = None,
               youtube_reach: int | None = None, duration_s: float | None = None,
               sources_with_data: list | None = None, quality: dict | None = None,
               overwrite: bool = True) -> dict:
    # A core source we asked for that returned nothing all run = an outage.
    missing = None
    if sources_with_data is not None:
        missing = sorted(s for s in sources if s in CORE_SOURCES and s not in sources_with_data) or None
    rec = {
        "date": date,
        "tag": tag or "",
        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
        "topics": len(per_topic),
        "sources_active": sources,
        "total_interactions": int(sum(per_topic.values())),
        "per_topic": per_topic,
        "bullets": bullets,
        "citations": citations,
        "source_interactions": source_interactions,
        "youtube_reach": youtube_reach,
        "duration_s": round(duration_s, 1) if duration_s is not None else None,
        "sources_with_data": sources_with_data,
        "missing_sources": missing,
        "quality": quality,
    }
    record(rec, overwrite=overwrite)
    return rec


# --------------------------------------------------------------------------
# Backfill from an already-rendered digest
# --------------------------------------------------------------------------
_SEC_RE = re.compile(r'<div class="stream">(.*?)</div><h2>(.*?)</h2>\s*(<ul>.*?</ul>)', re.DOTALL)
_SCORE_RE = re.compile(r"([\d,]+)\s*pts</span>")
_LI_RE = re.compile(r"<li>")
_A_RE = re.compile(r"<a href")
_META_SRC_RE = re.compile(r"keyless sources:\s*(.*?)\s*·")


def parse_digest(path: Path) -> dict | None:
    """Reconstruct a KPI record from a digest HTML (no source-level detail)."""
    h = path.read_text(encoding="utf-8")
    name = path.stem  # YYYY-MM-DD or YYYY-MM-DD-tag
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:-(.+))?$", name)
    if not m:
        return None
    date, tag = m.group(1), (m.group(2) or "")
    per_topic: dict[str, int] = {}
    for stream_badge, topic, _ul in _SEC_RE.findall(h):
        sc = _SCORE_RE.search(stream_badge)
        per_topic[topic] = int(sc.group(1).replace(",", "")) if sc else 0
    if not per_topic:
        return None
    srcs = _META_SRC_RE.search(h)
    sources = [s.strip() for s in srcs.group(1).split(",")] if srcs else []
    return {
        "date": date, "tag": tag,
        "ts": _dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "topics": len(per_topic), "sources_active": sources,
        "total_interactions": int(sum(per_topic.values())), "per_topic": per_topic,
        "bullets": len(_LI_RE.findall(h)), "citations": len(_A_RE.findall(h)),
        "source_interactions": None, "youtube_reach": None, "duration_s": None,
    }


def backfill_from_digests(digests_dir: Path) -> int:
    n = 0
    for f in sorted(digests_dir.glob("*.html")):
        rec = parse_digest(f)
        if rec:
            record(rec, overwrite=False)  # never clobber a richer live record
            n += 1
    return n


# --------------------------------------------------------------------------
# Dashboard (inline SVG)
# --------------------------------------------------------------------------
_CSS = """
:root{--bg:#0e0e10;--bg-elev:#18181b;--fg:#fafafa;--fg-muted:#a1a1aa;--fg-subtle:#71717a;
--accent:#a855f7;--accent-soft:#c4b5fd;--good:#34d399;--warn:#fbbf24;--bad:#fb7185;--border:#27272a;--max-w:1200px}
@media(prefers-color-scheme:light){:root{--bg:#fff;--bg-elev:#fafafa;--fg:#18181b;--fg-muted:#52525b;
--fg-subtle:#71717a;--accent:#7c3aed;--accent-soft:#6d28d9;--good:#059669;--warn:#b45309;--bad:#dc2626;--border:#e4e4e7}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);max-width:var(--max-w);
margin:0 auto;padding:3.5rem 1.5rem 6rem;font-family:'Inter',-apple-system,'Segoe UI',system-ui,sans-serif;
font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
.badge{display:inline-block;padding:.4rem .85rem;margin-bottom:.9rem;background:var(--bg-elev);
border:1px solid var(--border);border-radius:999px;font-family:ui-monospace,Consolas,monospace;
font-size:.78rem;color:var(--fg-muted)}.badge .accent{color:var(--accent)}
h1{font-size:1.6rem;margin:.2rem 0 .3rem}.sub{color:var(--fg-subtle);font-size:.88rem;margin-bottom:2rem;
font-family:ui-monospace,Consolas,monospace}
h2{font-size:1.05rem;margin:2.4rem 0 .6rem;color:var(--fg-muted);text-transform:uppercase;
letter-spacing:.06em;font-weight:600}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin:1rem 0}
.card{background:var(--bg-elev);border:1px solid var(--border);border-radius:12px;padding:1rem 1.1rem}
.card .v{font-size:1.55rem;font-weight:700;color:var(--accent-soft);line-height:1.1}
.card .k{color:var(--fg-subtle);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;margin-top:.35rem}
.chart{width:100%;height:auto;background:var(--bg-elev);border:1px solid var(--border);border-radius:12px;padding:.6rem}
.axl{fill:var(--fg-subtle);font-size:11px;font-family:ui-monospace,Consolas,monospace}
.axv{fill:var(--fg-muted);font-size:10px;font-family:ui-monospace,Consolas,monospace}
.axis{stroke:var(--border);stroke-width:1}
.foot{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--border);color:var(--fg-subtle);font-size:.78rem}
.banner{background:rgba(251,113,133,.1);border:1px solid var(--bad);border-radius:10px;padding:.7rem 1rem;
margin:0 0 1.5rem;font-size:.86rem;color:var(--fg)}
.banner strong{color:var(--bad)}
/* two-column: charts left, watch/read list right */
.layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:1.5rem;align-items:start}
.right{position:sticky;top:1.5rem}
.watch{background:var(--bg-elev);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.1rem 1.3rem;
max-height:calc(100vh - 3rem);overflow:auto}
.watch h2{margin:.1rem 0 .1rem}
.wl-sub{color:var(--fg-subtle);font-size:.72rem;margin-bottom:.6rem;font-family:ui-monospace,Consolas,monospace}
.wl-group{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--fg-subtle);margin:1rem 0 .35rem}
.wl-item{display:block;padding:.55rem .65rem;margin:.4rem 0;background:var(--bg);border:1px solid var(--border);
border-left:3px solid var(--accent);border-radius:8px;text-decoration:none;color:var(--fg)}
.wl-item:hover{border-color:var(--accent-soft)}
.wl-item.act{border-left-color:var(--good)}
.wl-item.watch{border-left-color:var(--warn)}
.wl-title{font-size:.84rem;font-weight:600;line-height:1.32}
.wl-meta{font-size:.7rem;color:var(--fg-subtle);margin-top:.3rem;font-family:ui-monospace,Consolas,monospace}
.wl-empty{color:var(--fg-subtle);font-size:.82rem}
.trend{display:grid;gap:.4rem}
.tr-item{display:flex;gap:.7rem;align-items:baseline;padding:.5rem .7rem;background:var(--bg-elev);border:1px solid var(--border);border-radius:8px;text-decoration:none;color:var(--fg)}
.tr-item:hover{border-color:var(--accent)}
.tr-rank{color:var(--accent);font-weight:700;font-family:ui-monospace,Consolas,monospace;min-width:1.4rem}
.tr-name{font-weight:600}
.tr-star{color:var(--warn);font-family:ui-monospace,Consolas,monospace;font-size:.82rem}
.tr-desc{display:block;color:var(--fg-subtle);font-size:.82rem;margin-top:.15rem}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.right{position:static}}
"""


def _card(value: str, label: str) -> str:
    return f'<div class="card"><div class="v">{value}</div><div class="k">{html.escape(label)}</div></div>'


def _bars(values, labels, w=900, h=240, pl=52, pb=42, pt=16, color="var(--accent)", flags=None) -> str:
    n = len(values) or 1
    maxv = max(list(values) + [1])
    pw, ph = w - pl - 16, h - pb - pt
    gap = pw / n
    bw = gap * 0.6
    out = [f'<line x1="{pl}" y1="{pt+ph}" x2="{w-16}" y2="{pt+ph}" class="axis"/>']
    for i, (v, lab) in enumerate(zip(values, labels)):
        x = pl + i * gap + (gap - bw) / 2
        bh = ph * (v / maxv) if maxv else 0
        y = pt + ph - bh
        bad = flags and i < len(flags) and flags[i]  # source-outage run
        col = "var(--warn)" if bad else color
        tip = f"{html.escape(lab)}: {v:,}" + (" ⚠ source outage — understated" if bad else "")
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{col}"><title>{tip}</title></rect>')
        mark = " ⚠" if bad else ""
        out.append(f'<text x="{x+bw/2:.1f}" y="{pt+ph+15:.1f}" text-anchor="middle" class="axl">{html.escape(lab)}{mark}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" text-anchor="middle" class="axv">{v:,}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{"".join(out)}</svg>'


def _area(values, labels, w=900, h=240, pl=52, pb=42, pt=16) -> str:
    n = len(values)
    maxv = max(list(values) + [1])
    pw, ph = w - pl - 16, h - pb - pt
    xs = [pl + pw / 2] if n == 1 else [pl + pw * i / (n - 1) for i in range(n)]
    ys = [pt + ph * (1 - v / maxv) for v in values]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    poly = f"{xs[0]:.1f},{pt+ph:.1f} {pts} {xs[-1]:.1f},{pt+ph:.1f}"
    out = [f'<line x1="{pl}" y1="{pt+ph}" x2="{w-16}" y2="{pt+ph}" class="axis"/>',
           f'<polygon points="{poly}" fill="var(--accent)" opacity="0.16"/>',
           f'<polyline points="{pts}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>']
    for x, y, lab, v in zip(xs, ys, labels, values):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="var(--accent)"><title>{html.escape(lab)}: {v:,}</title></circle>')
        out.append(f'<text x="{x:.1f}" y="{pt+ph+15:.1f}" text-anchor="middle" class="axl">{html.escape(lab)}</text>')
        out.append(f'<text x="{x:.1f}" y="{y-7:.1f}" text-anchor="middle" class="axv">{v:,}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{"".join(out)}</svg>'


def _hbars(pairs, w=900, rh=30, pl=120, color="var(--accent)") -> str:
    maxv = max([v for _, v in pairs] + [1])
    out = []
    for i, (lab, v) in enumerate(pairs):
        y = i * rh + 8
        bw = (w - pl - 90) * (v / maxv) if maxv else 0
        short = lab if len(lab) <= 42 else lab[:40] + "…"
        out.append(f'<text x="{pl-10}" y="{y+15}" text-anchor="end" class="axl">{html.escape(short)}</text>')
        out.append(f'<rect x="{pl}" y="{y+3}" width="{bw:.1f}" height="16" rx="3" fill="{color}"><title>{html.escape(lab)}: {v:,}</title></rect>')
        out.append(f'<text x="{pl+bw+6:.1f}" y="{y+15}" class="axv">{v:,}</text>')
    return f'<svg viewBox="0 0 {w} {len(pairs)*rh+16}" class="chart">{"".join(out)}</svg>'


_PALETTE = ["#a855f7", "#34d399", "#fbbf24", "#60a5fa", "#fb7185", "#2dd4bf", "#f472b6", "#a3e635"]


def _multiline(run_labels, series: dict, w=900, h=300, pl=52, pb=72, pt=16) -> str:
    """One line per category (stream/topic) across runs, with a wrapped legend."""
    maxv = max([v for vals in series.values() for v in vals] + [1])
    n = len(run_labels)
    pw, ph = w - pl - 16, h - pb - pt
    xs = [pl + pw / 2] if n == 1 else [pl + pw * i / (n - 1) for i in range(n)]
    out = [f'<line x1="{pl}" y1="{pt+ph}" x2="{w-16}" y2="{pt+ph}" class="axis"/>']
    for x, lab in zip(xs, run_labels):
        out.append(f'<text x="{x:.1f}" y="{pt+ph+15:.1f}" text-anchor="middle" class="axl">{html.escape(lab)}</text>')
    for si, (name, vals) in enumerate(series.items()):
        c = _PALETTE[si % len(_PALETTE)]
        ys = [pt + ph * (1 - v / maxv) for v in vals]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2.5"/>')
        for x, y, v in zip(xs, ys, vals):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}"><title>{html.escape(name)}: {v:,}</title></circle>')
    lx, ly = pl, pt + ph + 36
    for si, name in enumerate(series.keys()):
        c = _PALETTE[si % len(_PALETTE)]
        short = name if len(name) <= 24 else name[:22] + "…"
        out.append(f'<rect x="{lx:.1f}" y="{ly-9:.1f}" width="11" height="11" rx="2" fill="{c}"/>')
        out.append(f'<text x="{lx+16:.1f}" y="{ly:.1f}" class="axl">{html.escape(short)}</text>')
        lx += 30 + len(short) * 6.6
        if lx > w - 170:
            lx, ly = pl, ly + 18
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{"".join(out)}</svg>'


def _label(r: dict) -> str:
    d = r.get("date", "")[5:]
    return f"{d} {r['tag']}".strip() if r.get("tag") else d


# --------------------------------------------------------------------------
# Read / Watch list — actionable items (Act + Watch verdicts) from a digest
# --------------------------------------------------------------------------
_WL_SECTION_RE = re.compile(r"<h2>(.*?)</h2>\s*(<ul>.*?</ul>)", re.DOTALL)
_WL_LI_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)
_STRIP_TAGS = re.compile(r"<[^>]+>")


def extract_watchlist(digest_html: str) -> list[dict]:
    """Pull Act/Watch bullets (skip Ignore) from a rendered digest, prioritized."""
    items = []
    for topic, ul in _WL_SECTION_RE.findall(digest_html):
        topic = html.unescape(_STRIP_TAGS.sub("", topic))
        for li in _WL_LI_RE.findall(ul):
            vm = re.search(r'class="v-(act|ignore|watch)"', li)
            verdict = vm.group(1) if vm else "watch"
            if verdict == "ignore":
                continue
            tm = re.search(r"<strong>(.*?)</strong>", li, re.DOTALL)
            title = html.unescape(_STRIP_TAGS.sub("", tm.group(1))) if tm else "(untitled)"
            am = re.search(r'<a href="(.*?)">(.*?)</a>', li, re.DOTALL)
            url = am.group(1) if am else ""
            source = html.unescape(_STRIP_TAGS.sub("", am.group(2))) if am else ""
            pm = re.search(r'class="pts">[^\d]*([\d,]+)', li)
            pts = int(pm.group(1).replace(",", "")) if pm else 0
            items.append({"verdict": verdict, "title": title, "url": url,
                          "source": source, "pts": pts, "topic": topic})
    items.sort(key=lambda x: ({"act": 0, "watch": 1}.get(x["verdict"], 9), -x["pts"]))
    return items


def _watchlist_html(items: list[dict] | None) -> str:
    panel_head = ('<aside class="right"><div class="watch"><h2>Read / Watch list</h2>'
                  '<div class="wl-sub">latest run · Act + Watch · highest-backed first</div>')
    if not items:
        return panel_head + '<div class="wl-empty">No Act/Watch items in the latest run.</div></div></aside>'
    rows, cur = [], None
    for it in items:
        if it["verdict"] != cur:
            cur = it["verdict"]
            rows.append(f'<div class="wl-group">{"🎯 Act on" if cur == "act" else "👀 Watch / read"}</div>')
        meta = html.escape(it["source"] or it["topic"])
        if it["pts"]:
            meta += f" · ▣ {it['pts']:,}"
        meta += f" · {html.escape(it['topic'])}"
        href = f' href="{html.escape(it["url"])}" target="_blank" rel="noopener"' if it["url"] else ""
        rows.append(
            f'<a class="wl-item {it["verdict"]}"{href}>'
            f'<div class="wl-title">{html.escape(it["title"])}</div>'
            f'<div class="wl-meta">{meta}</div></a>'
        )
    return panel_head + "".join(rows) + "</div></aside>"


def _cfd(labels, series, w=900, h=320, pl=52, pb=80, pt=16) -> str:
    """Stacked cumulative-flow area: one band per stream, cumulative over runs."""
    names = list(series)
    n = len(labels)
    totals = [sum(series[s][i] for s in names) for i in range(n)] or [0]
    maxv = max(totals + [1])
    pw, ph = w - pl - 16, h - pb - pt
    xs = [pl + pw / 2] if n == 1 else [pl + pw * i / (n - 1) for i in range(n)]
    Y = lambda v: pt + ph * (1 - v / maxv)  # noqa: E731
    out = [f'<line x1="{pl}" y1="{pt+ph}" x2="{w-16}" y2="{pt+ph}" class="axis"/>']
    lower = [0.0] * n
    for si, s in enumerate(names):
        upper = [lower[i] + series[s][i] for i in range(n)]
        up = " ".join(f"{xs[i]:.1f},{Y(upper[i]):.1f}" for i in range(n))
        dn = " ".join(f"{xs[i]:.1f},{Y(lower[i]):.1f}" for i in range(n - 1, -1, -1))
        c = _PALETTE[si % len(_PALETTE)]
        cum = (upper[-1] - lower[-1]) if n else 0
        out.append(f'<polygon points="{up} {dn}" fill="{c}" opacity="0.82" stroke="{c}" stroke-width="1">'
                   f'<title>{html.escape(s)}: {cum:,.0f} cumulative</title></polygon>')
        lower = upper
    step = max(1, n // 8)
    for i in range(0, n, step):
        out.append(f'<text x="{xs[i]:.1f}" y="{pt+ph+15:.1f}" text-anchor="middle" class="axl">{html.escape(labels[i])}</text>')
    lx, ly = pl, pt + ph + 42
    for si, s in enumerate(names):
        c = _PALETTE[si % len(_PALETTE)]
        short = s if len(s) <= 28 else s[:26] + "…"
        out.append(f'<rect x="{lx:.1f}" y="{ly-9:.1f}" width="11" height="11" rx="2" fill="{c}"/>')
        out.append(f'<text x="{lx+16:.1f}" y="{ly:.1f}" class="axl">{html.escape(short)}</text>')
        lx += 30 + len(short) * 6.6
        if lx > w - 200:
            lx, ly = pl, ly + 18
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{"".join(out)}</svg>'


def _trending_html(items: list[dict] | None) -> str:
    if not items:
        return ""
    rows = []
    for i, it in enumerate(items, 1):
        lang = f' · {html.escape(it["lang"])}' if it.get("lang") else ""
        rows.append(
            f'<a class="tr-item" href="{html.escape(it["url"])}" target="_blank" rel="noopener">'
            f'<span class="tr-rank">{i}</span><span>'
            f'<span class="tr-name">{html.escape(it["name"])}</span> '
            f'<span class="tr-star">★ {it["stars"]:,} {html.escape(it.get("stars_label", ""))}</span>{lang}'
            f'<span class="tr-desc">{html.escape(it.get("desc", ""))}</span></span></a>'
        )
    return f'<h2>Top {len(items)} trending AI repos this week</h2><div class="trend">{"".join(rows)}</div>'


def render_dashboard(records: list[dict] | None = None, topic_streams: dict | None = None,
                     watchlist: list[dict] | None = None, trending: list[dict] | None = None) -> Path:
    runs = sorted(records if records is not None else load_all(),
                  key=lambda r: (r.get("date", ""), r.get("tag", ""), r.get("ts", "")))
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().isoformat()
    if not runs:
        DASHBOARD.write_text(
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{_CSS}</style></head>"
            f"<body><h1>QE Research KPIs</h1><p>No runs recorded yet.</p></body></html>",
            encoding="utf-8")
        return DASHBOARD

    labels = [_label(r) for r in runs]
    totals = [r["total_interactions"] for r in runs]
    cum, run_sum = [], 0
    for t in totals:
        run_sum += t
        cum.append(run_sum)
    latest = runs[-1]

    cum_reach = sum(r.get("youtube_reach") or 0 for r in runs)
    latest_missing = latest.get("missing_sources")
    swd = latest.get("sources_with_data")
    health = (f'{sum(1 for s in CORE_SOURCES if s in swd)}/{len(CORE_SOURCES)}'
              if swd is not None else "—")
    health_val = (f'<span class="b">{health} ⚠</span>' if latest_missing else health)

    # Digest quality (3-judge panel). green ≥80 · amber 60-79 · red <60.
    def _qspan(v):
        if v is None:
            return "—"
        color = "var(--good)" if v >= 80 else ("var(--warn)" if v >= 60 else "var(--bad)")
        return f'<span style="color:{color};font-weight:700">{v}</span>'
    lq = latest.get("quality") or {}
    composite = lq.get("composite")
    faith = lq.get("faithfulness")

    cards = "".join([
        _card(f"{cum[-1]:,}", "cumulative interactions"),
        _card(str(len(runs)), "runs tracked"),
        _card(f"{latest['total_interactions']:,}", "latest run interactions"),
        _card(_qspan(composite), "digest quality (latest)"),
        _card(str(latest["topics"]), "topics (latest run)"),
        _card(health_val, "source health (latest)"),
        _card(str(latest["citations"]), "citations (latest run)"),
        _card(f"{cum_reach:,}" if cum_reach else "—", "youtube reach (views)"),
    ])
    banner = ""
    if latest_missing:
        names = ", ".join(s.replace("hackernews", "Hacker News").title() for s in latest_missing)
        banner += (f'<div class="banner">⚠ Source outage on the latest run — <strong>{html.escape(names)}</strong> '
                   f'returned no data. Interaction totals are understated; this is a data-availability gap, not a signal drop.</div>')
    if faith is not None and faith < 70:
        banner += (f'<div class="banner">⚠ Low <strong>faithfulness ({faith}/100)</strong> on the latest digest — '
                   f'possible unsupported or fabricated citations. Review before trusting.</div>')

    if trending is None:
        try:
            import trending as _tr
            trending = _tr.fetch_trending()
        except Exception:  # noqa: BLE001
            trending = []
    # Cumulative Flow Diagram: cumulative interactions per stream over the last
    # ~14 runs (2-week trend) — each stream is a stacked band.
    cfd_runs = runs[-14:]
    cfd_labels = [_label(r) for r in cfd_runs]
    if topic_streams:
        seen: list[str] = []
        for r in cfd_runs:
            for t in r.get("per_topic", {}):
                s = topic_streams.get(t, "Other")
                if s not in seen:
                    seen.append(s)
        cfd_series = {s: [] for s in seen}
        tot = {s: 0 for s in seen}
        for r in cfd_runs:
            add = {s: 0 for s in seen}
            for t, v in r.get("per_topic", {}).items():
                s = topic_streams.get(t, "Other")
                add[s] = add.get(s, 0) + v
            for s in seen:
                tot[s] += add.get(s, 0)
                cfd_series[s].append(tot[s])
        cfd_chart = _cfd(cfd_labels, cfd_series)
    else:
        cfd_chart = _area(cum, labels)

    blocks = [
        _trending_html(trending),
        f'<h2>Cumulative flow — interactions by stream (2-week trend)</h2>{cfd_chart}',
        f'<h2>Interactions per run</h2>{_bars(totals, labels, flags=[bool(r.get("missing_sources")) for r in runs])}',
    ]

    # Digest quality trend (composite 0-100 per run), shown once any run is judged.
    comp_series = [(r.get("quality") or {}).get("composite") or 0 for r in runs]
    if any(comp_series):
        blocks.append(f'<h2>Digest quality (composite / run)</h2>{_bars(comp_series, labels)}')

    # Per-category trends across runs (one line per stream / topic).
    if topic_streams:
        sstats: dict[str, list] = {}
        for i, r in enumerate(runs):
            for t, v in r.get("per_topic", {}).items():
                s = topic_streams.get(t, "Other")
                sstats.setdefault(s, [0] * len(runs))[i] += v
        blocks.append(f'<h2>Stream trend (interactions / run)</h2>{_multiline(labels, sstats)}')
    # Category breakdowns (the bread and butter): latest run by topic + by stream.
    by_topic = sorted(latest.get("per_topic", {}).items(), key=lambda kv: kv[1], reverse=True)
    if by_topic:
        blocks.append(f'<h2>By topic — latest run ({_label(latest)})</h2>{_hbars(by_topic, pl=280)}')
    if topic_streams:
        by_stream: dict[str, int] = {}
        for t, v in latest.get("per_topic", {}).items():
            by_stream[topic_streams.get(t, "Other")] = by_stream.get(topic_streams.get(t, "Other"), 0) + v
        pairs = sorted(by_stream.items(), key=lambda kv: kv[1], reverse=True)
        blocks.append(f'<h2>By stream — latest run</h2>{_hbars(pairs, pl=300, color="var(--good)")}')

    if latest.get("source_interactions"):
        pairs = sorted(latest["source_interactions"].items(), key=lambda kv: kv[1], reverse=True)
        blocks.append(f'<h2>Source mix (latest run)</h2>{_hbars([(k, v) for k, v in pairs])}')

    DASHBOARD.write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QE Research KPIs</title><style>{_CSS}</style></head><body>
<div class="badge">📈 qe research loop · <span class="accent">KPI dashboard</span> · {today}</div>
<h1>Research KPIs</h1>
<div class="sub">{len(runs)} runs · {labels[0]} → {labels[-1]} · interactions = upvotes + points + reactions + comments</div>
{banner}
<div class="layout">
<main class="left">
<div class="cards">{cards}</div>
{''.join(blocks)}
</main>
{_watchlist_html(watchlist)}
</div>
<div class="foot">Data: metrics/kpi.jsonl · rebuild: <code>python src/orchestrator.py kpi</code>. Each run also updates this dashboard automatically.</div>
</body></html>""", encoding="utf-8")
    return DASHBOARD
