"""Render the daily digest as one self-contained dark-mode HTML file.

The palette is styled after the last30days `--emit=html` brief
(html_render.py: --bg #0e0e10, accent #a855f7) so the digest matches the
engine's shareable look, but this is our own minimal renderer — no engine
import, no external assets, everything inline.
"""
from __future__ import annotations

import html
import re

CSS = """
:root{--bg:#0e0e10;--bg-elev:#18181b;--fg:#fafafa;--fg-muted:#a1a1aa;
--fg-subtle:#71717a;--accent:#a855f7;--accent-soft:#c4b5fd;--border:#27272a;
--good:#34d399;--warn:#fbbf24;--bad:#fb7185;--max-w:760px}
@media (prefers-color-scheme:light){:root{--bg:#fff;--bg-elev:#fafafa;--fg:#18181b;
--fg-muted:#52525b;--fg-subtle:#71717a;--accent:#7c3aed;--accent-soft:#6d28d9;--border:#e4e4e7;
--good:#059669;--warn:#b45309;--bad:#dc2626}}
*{box-sizing:border-box}html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);
font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;
font-size:17px;line-height:1.65;-webkit-font-smoothing:antialiased}
body{max-width:var(--max-w);margin:0 auto;padding:3.5rem 1.5rem 6rem}
.badge{display:inline-block;padding:.4rem .85rem;margin-bottom:.75rem;background:var(--bg-elev);
border:1px solid var(--border);border-radius:999px;font-family:ui-monospace,'Cascadia Code',Consolas,monospace;
font-size:.8rem;color:var(--fg-muted)}
.badge .accent{color:var(--accent)}
.meta{color:var(--fg-subtle);font-size:.85rem;margin-bottom:2.5rem;
font-family:ui-monospace,'Cascadia Code',Consolas,monospace}
h2{font-size:1.25rem;margin:2.5rem 0 .25rem;color:var(--fg)}
.stream{color:var(--fg-subtle);font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.75rem}
.score{color:var(--accent-soft);font-weight:600}
ul{padding-left:1.1rem;margin:.5rem 0 0}li{margin:.55rem 0}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}
a:hover{border-bottom-color:var(--accent)}
strong{color:var(--fg);font-weight:600}em{color:var(--accent-soft);font-style:normal}
.v-act{color:var(--good);font-weight:700}
.v-ignore{color:var(--bad);font-weight:700}
.v-watch{color:var(--warn);font-weight:700}
.pts{color:var(--fg-muted);font-family:ui-monospace,'Cascadia Code',Consolas,monospace;font-size:.8rem;white-space:nowrap}
.foot{margin-top:4rem;padding-top:1.5rem;border-top:1px solid var(--border);
color:var(--fg-subtle);font-size:.8rem}
"""


# Traffic-light verdicts so triage jumps out: green = do it, red = skip, amber = watch.
_VERDICT_CLASS = {
    "act": "v-act", "yes": "v-act", "do": "v-act", "adopt": "v-act", "use": "v-act",
    "ignore": "v-ignore", "no": "v-ignore", "skip": "v-ignore", "drop": "v-ignore",
}


def _color_verdict(m: re.Match) -> str:
    word = m.group(2)
    cls = _VERDICT_CLASS.get(word.lower(), "v-watch")  # Skim/Watch/Track/Monitor -> amber
    return f'{m.group(1)}<span class="{cls}">{word}</span>'


def _inline(s: str) -> str:
    s = html.escape(s)
    # Stash links so bold/italic transforms can't mangle underscores inside URLs.
    links: list[str] = []

    def _stash(m: re.Match) -> str:
        links.append(f'<a href="{m.group(2)}">{m.group(1)}</a>')
        return f"\x00{len(links) - 1}\x00"

    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", _stash, s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"_([^_]+)_", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    # Color the verdict word right after "Act or ignore:".
    s = re.sub(r"(Act or ignore:\s*</em>\s*|Act or ignore:\s*)([A-Za-z]+)", _color_verdict, s)
    for i, link in enumerate(links):
        s = s.replace(f"\x00{i}\x00", link)
    return s


# Lines that are engine footer / separators, not bullets — never rendered.
_NOISE_PREFIX = ("---", "✅", "├─", "└─", "│", "<!--", "#")


def _lookup(points: dict, url: str) -> int:
    return points.get(url) or points.get(url.rstrip("/")) or 0


def _bullets(md: str, points: dict | None = None) -> str:
    points = points or {}
    items = []
    for line in md.splitlines():
        line = line.strip()
        if not line or line.startswith(_NOISE_PREFIX):
            continue
        # Keep only real bullet lines (drops stray preamble/footer prose).
        if not re.match(r"^(?:[-*]|\d+\.)\s+", line):
            continue
        line = re.sub(r"^(?:[-*]|\d+\.)\s+", "", line)
        urls = re.findall(r"\((https?://[^)\s]+)\)", line)
        pts = max((_lookup(points, u) for u in urls), default=0)
        inner = _inline(line)
        if pts:  # backing engagement of the cited item, alongside the verdict
            chip = f'<span class="pts">▣ {pts:,} pts</span>'
            if "<a href" in inner:
                inner = re.sub(r"\s*(<a href)", f" · {chip} \\1", inner, count=1)
            else:
                inner = f"{inner} · {chip}"
        items.append(f"<li>{inner}</li>")
    return "<ul>\n" + "\n".join(items) + "\n</ul>" if items else "<p>(no synthesis)</p>"


# A brief's leading verdict line: '_<label>:_ **Word** - reason'. The label varies by
# lane (Act or ignore / Worth it / Restaurant at home), so match the shape, not the words.
_VERDICT_LINE_RE = re.compile(r"^_[^_]+:_\s*\*\*\S")


def _verdict_line(md_line: str) -> str:
    """Render the top '_<label>:_ **Word** - reason' verdict line as a colored chip.

    Colors the first bold token (the verdict word) by its traffic-light meaning, so
    every lane's verdict — Act/Watch/Ignore, Nails it/Close/Hard — reads at a glance.
    """
    inner = _inline(md_line)

    def _color(m: re.Match) -> str:
        cls = _VERDICT_CLASS.get(m.group(1).split()[0].lower(), "v-watch")
        return f'<strong class="{cls}">{m.group(1)}</strong>'

    inner = re.sub(r"<strong>([^<]+)</strong>", _color, inner, count=1)
    return f'<div class="verdict">{inner}</div>'


def render_brief(tool: str, sections_md: str, sources: list[str],
                 meta: dict | None = None, points: dict | None = None) -> str:
    """Render a standalone due-diligence brief: verdict + 4 `## ` sections + footer.

    sections_md is the markdown from duediligence.synthesize_dd. Reuses the same
    CSS, inline-link, and verdict-color helpers as the daily digest so briefs
    match the dashboard look. Self-contained dark-mode HTML.
    """
    meta = meta or {}
    date_str = meta.get("date", "")
    # Lane-customizable chrome. Defaults preserve the original tool-dd output
    # byte-for-byte, so the dd / agentdd / recipe / todo lanes are unaffected.
    kind = meta.get("kind", "tool due-diligence")
    emoji = meta.get("emoji", "🔎")
    title = meta.get("title", f"Tool Due-Diligence - {tool}")
    rerun = meta.get("rerun", f'python src/orchestrator.py dd "{tool}"')
    lines = sections_md.splitlines()
    verdict_html = ""
    footer_md: list[str] = []
    section_lines: list[str] = []
    in_footer = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("---") or stripped.startswith("✅"):
            in_footer = True
        if in_footer:
            footer_md.append(ln)
            continue
        if not verdict_html and _VERDICT_LINE_RE.match(stripped):
            verdict_html = _verdict_line(stripped)
            continue
        section_lines.append(ln)

    # Split the remaining body into `## ` sections, render each with _bullets().
    body: list[str] = []
    cur_title: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        if cur_title is not None:
            body.append(f"<h2>{html.escape(cur_title)}</h2>\n{_bullets(chr(10).join(buf), points)}")

    for ln in section_lines:
        if ln.lstrip().startswith("## "):
            _flush()
            cur_title = ln.lstrip()[3:].strip()
            buf = []
        elif ln.lstrip().startswith("# "):
            continue  # drop any stray H1; the badge is the title
        else:
            buf.append(ln)
    _flush()

    footer_html = ""
    if footer_md:
        clean = "\n".join(l for l in footer_md if l.strip() and not l.strip().startswith("---"))
        if clean.strip():
            footer_html = f'<pre class="tree">{html.escape(clean)}</pre>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}
.verdict{{font-size:1.05rem;margin:.5rem 0 2rem;padding:.75rem 1rem;background:var(--bg-elev);
border:1px solid var(--border);border-radius:10px}}
.tree{{margin-top:2.5rem;padding:1rem;background:var(--bg-elev);border:1px solid var(--border);
border-radius:10px;color:var(--fg-muted);font-family:ui-monospace,'Cascadia Code',Consolas,monospace;
font-size:.8rem;white-space:pre-wrap;overflow-x:auto}}</style></head><body>
<div class="badge">{emoji} {html.escape(kind)} · <span class="accent">{html.escape(tool)}</span></div>
<div class="meta">last 30 days · keyless sources: {html.escape(', '.join(sources))} · synthesized via Claude Code{(' · ' + html.escape(date_str)) if date_str else ''}</div>
{verdict_html}
{chr(10).join(body)}
{footer_html}
<div class="foot">{html.escape(kind.capitalize())} brief over the last30days engine. Keyless sources only
(Reddit, Hacker News, Polymarket, GitHub, YouTube). Re-run: <code>{html.escape(rerun, quote=False)}</code>.</div>
</body></html>"""


def render(date_str: str, sections: list[dict], sources: list[str], points: dict | None = None) -> str:
    body = []
    for sec in sections:
        score = sec.get("score")
        tag = f' · <span class="score">▣ {score:,} pts</span>' if score is not None else ""
        body.append(
            f'<div class="stream">{html.escape(sec.get("stream",""))}{tag}</div>'
            f"<h2>{html.escape(sec['topic'])}</h2>\n{_bullets(sec['md'], points)}"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Research Digest - {date_str}</title>
<style>{CSS}</style></head><body>
<div class="badge">🛰️ daily research loop · <span class="accent">{date_str}</span></div>
<div class="meta">last 30 days · keyless sources: {html.escape(', '.join(sources))} · synthesized via Claude Code · sorted by relevance (▣ total engagement)</div>
{chr(10).join(body)}
<div class="foot">Generated by research-loop over the last30days engine. Keyless sources only
(Reddit, Hacker News, Polymarket, GitHub, YouTube). Re-run: <code>python src/orchestrator.py run</code>.</div>
</body></html>"""
