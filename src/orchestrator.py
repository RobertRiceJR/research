#!/usr/bin/env python3
"""Daily Research Loop — thin orchestrator over the last30days engine.

v0 scope: prove ONE research stream end to end (AI / my stack).

SECURITY BOUNDARY (do not weaken without review):
  * Only the four KEYLESS sources are ever requested: reddit, hackernews,
    polymarket, github. github is auto-included only when `gh`/GITHUB_TOKEN
    is present (mirrors the engine's own gating).
  * The engine subprocess runs with a SCRUBBED environment: every key/cookie
    var that could activate a non-keyless source is stripped, and
    EXCLUDE_SOURCES bans the rest. So even if this machine later has X /
    ScrapeCreators / Brave keys, the engine cannot reach those sources.
  * We NEVER pass --x-handle / --x-related / --tiktok-* / --ig-* / --auto-resolve,
    and we never import the engine's chrome_cookies / safari_cookies /
    cookie_extract modules. We only shell out to its documented CLI.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Resolved, machine-verified paths (baked in so a fresh session / scheduled
# run never has to re-diagnose). Each falls back to PATH discovery if moved.
# --------------------------------------------------------------------------
# Self-contained: the keyless engine is vendored in this repo under engine/
# (a pruned fork of mvanhorn/last30days-skill — see engine/VENDORED.md).
ENGINE_SCRIPT = Path(__file__).resolve().parent.parent / "engine" / "last30days.py"
GH_DIR = r"C:\Program Files\GitHub CLI"
PY313 = Path(r"C:\Users\terri\AppData\Local\Programs\Python\Python313\python.exe")

# The keyless allowlist. This tuple is the security contract.
# youtube is keyless too — yt-dlp public search needs no API key and no cookies.
KEYLESS_SOURCES = ("reddit", "hackernews", "polymarket", "github", "youtube")

# Sources explicitly banned from the engine, belt-and-suspenders on top of
# the allowlist + scrubbed env. (youtube intentionally NOT here — it's keyless.)
EXCLUDE_SOURCES = (
    "x,tiktok,instagram,threads,bluesky,truthsocial,"
    "perplexity,pinterest,xiaohongshu,digg,xquik"
)

# Env vars that could unlock a non-keyless source — stripped before the engine runs.
BLOCKED_ENV = (
    "SCRAPECREATORS_API_KEY", "AUTH_TOKEN", "CT0", "FROM_BROWSER",
    "XAI_API_KEY", "OPENAI_API_KEY", "BSKY_HANDLE", "BSKY_APP_PASSWORD",
    "TRUTHSOCIAL_TOKEN", "BRAVE_API_KEY", "EXA_API_KEY", "SERPER_API_KEY",
    "PARALLEL_API_KEY", "OPENROUTER_API_KEY", "APIFY_API_TOKEN",
    "GOOGLE_API_KEY", "GEMINI_API_KEY",
)

# The engine emits UTF-8 (emoji tree, etc.); Windows defaults to cp1252.
# Force UTF-8 on the console so prints of engine output never crash.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "topics.yaml"
DIGESTS = ROOT / "digests"
RAW = ROOT / "raw"


# --------------------------------------------------------------------------
# Tiny YAML-subset reader (zero dependencies — nothing to pip install, so a
# fresh session is never held up). Supports exactly the topics.yaml schema:
# a top-level `streams:` map, each stream a map of scalars + a `topics:` list.
# --------------------------------------------------------------------------
def _scalar(raw: str):
    raw = raw.strip()
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    return raw


def load_topics(path: Path = CONFIG) -> dict:
    streams: dict[str, dict] = {}
    cur: dict | None = None
    in_topics = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `streams:`
            continue
        if indent == 2 and text.endswith(":"):  # stream name
            cur = {"enabled": False, "label": text[:-1], "topics": []}
            streams[text[:-1]] = cur
            in_topics = False
            continue
        if cur is None:
            continue
        if indent == 4:
            if text == "topics:":
                in_topics = True
                continue
            in_topics = False
            key, _, val = text.partition(":")
            cur[key.strip()] = _scalar(val)
            continue
        if indent >= 6 and in_topics and text.startswith("- "):
            cur["topics"].append(_scalar(text[2:]))
    return streams


# --------------------------------------------------------------------------
# Runtime resolution
# --------------------------------------------------------------------------
def resolve_python() -> str:
    """A Python 3.12+ interpreter for the engine (its hard requirement)."""
    if sys.version_info >= (3, 12):
        return sys.executable
    if PY313.exists():
        return str(PY313)
    for name in ("python3.13", "python3.12", "py"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit(
        "ERROR: the last30days engine needs Python 3.12+. None found.\n"
        f"Install Python 3.13, or restore {PY313}."
    )


def engine_env() -> dict:
    """A scrubbed environment that can ONLY reach keyless sources."""
    env = dict(os.environ)
    for key in BLOCKED_ENV:
        env.pop(key, None)
    # Ensure `gh` resolves for the engine (winget puts it here; the parent
    # shell may have a stale PATH that omits it).
    if os.path.isdir(GH_DIR):
        env["PATH"] = GH_DIR + os.pathsep + env.get("PATH", "")
    # Ensure `yt-dlp` resolves (installed into the engine python's Scripts dir,
    # which pip warns is not on PATH). Gates the keyless YouTube source.
    for scripts in {PY313.parent / "Scripts", Path(sys.executable).parent / "Scripts"}:
        if scripts.is_dir():
            env["PATH"] = str(scripts) + os.pathsep + env["PATH"]
    env["EXCLUDE_SOURCES"] = EXCLUDE_SOURCES
    return env


def available_sources(py: str, env: dict) -> list[str]:
    """Ask the engine what it can reach, intersect with the keyless allowlist."""
    try:
        out = subprocess.run(
            [py, str(ENGINE_SCRIPT), "--diagnose"],
            env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        data = json.loads(out.stdout)
        avail = data.get("available_sources", [])
    except Exception:
        avail = ["reddit", "hackernews", "polymarket"]
    return [s for s in KEYLESS_SOURCES if s in avail]


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


# Relevance = total community engagement the engine tallied in its footer tree
# (e.g. "1,243 upvotes │ 1,189 points │ 4,092 reactions │ 862 comments").
# Per-item evidence uses `pts`/`cmt`, so matching the full words hits the
# authoritative footer aggregate only — no double counting.
_ENGAGEMENT_RE = re.compile(r"(\d[\d,]*)\s+(?:upvotes|points|reactions|comments)\b", re.IGNORECASE)


def _relevance_score(md: str) -> int:
    return sum(int(n.replace(",", "")) for n in _ENGAGEMENT_RE.findall(md))


# Per-item engagement (interactions only — excludes views/likes so a bullet's
# points stay on the same scale as the topic total). Maps each evidence URL to
# its backing engagement for the per-bullet chip.
_ITEM_ENG_RE = re.compile(r"(\d[\d,]*)\s*(?:pts|points|upvotes|reactions|cmt|comments)\b", re.IGNORECASE)
_URL_LINE_RE = re.compile(r"URL:\s*(https?://\S+)")


def points_index(raw_md: str) -> dict:
    idx: dict[str, int] = {}
    cur = 0
    for ln in raw_md.splitlines():
        if "[" in ln and _ITEM_ENG_RE.search(ln):  # an item's engagement line
            cur = sum(int(n.replace(",", "")) for n in _ITEM_ENG_RE.findall(ln))
        m = _URL_LINE_RE.search(ln)
        if m:  # URL line follows the engagement line; bind, then reset
            idx[m.group(1).rstrip(").,")] = cur
            cur = 0
    return idx


# --------------------------------------------------------------------------
# Engine + synthesis
# --------------------------------------------------------------------------
_PLAN_INSTRUCTION = (
    "You are the query planner for a 30-day social/web research engine. Output ONLY a JSON object "
    "(no prose, no code fences) with this shape: "
    '{"intent":"factual|product|concept|opinion|how_to|comparison|breaking_news|prediction",'
    '"freshness_mode":"strict_recent|balanced_recent|evergreen_ok",'
    '"cluster_mode":"none|story|workflow|market|debate",'
    '"subqueries":[{"label":"short","search_query":"keyword-heavy query","ranking_query":"natural-language question","sources":["reddit"],"weight":1.0}]}. '
    "Rules: emit 3-5 paraphrased subqueries that each express the intent differently (broad retrieval, narrow ranking); "
    "every subquery needs both search_query and ranking_query; sources must be drawn ONLY from the AVAILABLE sources "
    "given on stdin; preserve exact proper nouns; NEVER put temporal words (recent, last 30 days, month/year) or "
    "meta words (news, updates, latest) in search_query. Return JSON only."
)


def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    return obj if isinstance(obj, dict) and obj.get("subqueries") else None
                except json.JSONDecodeError:
                    return None
    return None


# Short, ASCII-only directive passed as the `claude -p` argument. The heavy
# instruction (with quotes/pipes/braces) goes in stdin to dodge cmd.exe quoting.
_CLAUDE_DIRECTIVE = "Read the instructions and data below, then output only what they ask for. Output nothing else."


def _run_claude(body: str, timeout: int) -> str:
    """Headless Claude Code call: short directive in -p, heavy prompt via stdin."""
    claude = shutil.which("claude")
    if not claude:
        return ""
    cmd = [claude, "-p", _CLAUDE_DIRECTIVE, "--output-format", "text"]
    if claude.lower().endswith((".cmd", ".bat")):
        cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c"] + cmd
    try:
        proc = subprocess.run(
            cmd, input=body, text=True, capture_output=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return (proc.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def generate_plan(topic: str, sources: list[str], raw_dir: Path) -> Path | None:
    """Have Claude author a JSON query plan so the engine skips degraded fallback.

    LAW 7: the hosting reasoning model is the planner — no LLM provider key needed.
    Returns a plan file path, or None to fall back to the bare/quick path.
    """
    body = f"{_PLAN_INSTRUCTION}\n\nTOPIC: {topic}\nAVAILABLE sources: {', '.join(sources)}"
    try:
        plan = _extract_json(_run_claude(body, timeout=120))
        if not plan:
            return None
        # Keep only allowed sources in each subquery (defense in depth).
        for sq in plan.get("subqueries", []):
            sq["sources"] = [s for s in sq.get("sources", []) if s in sources] or list(sources)
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{_slug(topic)}-plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path
    except Exception:  # noqa: BLE001
        return None


def run_engine(
    py: str, env: dict, topic: str, sources: list[str], raw_dir: Path,
    plan_path: Path | None = None,
) -> str:
    """Run the engine for one topic, keyless. Returns the markdown report."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        py, str(ENGINE_SCRIPT), topic,
        "--emit=md",
        f"--search={','.join(sources)}",
        "--save-dir", str(raw_dir),
    ]
    if plan_path:
        # Plan present: default depth so the multiple sub-queries survive
        # (--quick would truncate the plan to a single sub-query).
        cmd += ["--plan", str(plan_path)]
    else:
        cmd.append("--quick")
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600
    )
    md = proc.stdout or ""
    (raw_dir / f"{_slug(topic)}-raw.md").write_text(md, encoding="utf-8")
    if not md.strip():
        md = f"(engine returned no output for '{topic}')\n{(proc.stderr or '')[:500]}"
    return md


_SYNTH_INSTRUCTION = (
    "You are summarizing 30-day social/web research for a daily digest. The TOPIC and the raw "
    "ranked evidence (Reddit, Hacker News, Polymarket, GitHub, YouTube) arrive below. Output EXACTLY 5 "
    "markdown bullets, one line each, no preamble. Each bullet format: '- **<what changed>** - "
    "<why it matters> - _Act or ignore:_ <one word> (<3-5 word reason>) [<source>](<url>)'. Every "
    "bullet MUST end with at least one inline markdown link copied VERBATIM from a URL in the "
    "evidence; never invent a URL. If evidence is thin for the topic, say so in the bullet."
)


def synthesize(topic: str, raw_md: str) -> str:
    """Turn raw evidence into 5 cited bullets via headless Claude Code."""
    if not shutil.which("claude"):
        return "- _Synthesis skipped: `claude` CLI not found on PATH. Raw evidence saved._"
    body = f"{_SYNTH_INSTRUCTION}\n\nTOPIC: {topic}\n\nEVIDENCE:\n{raw_md}"
    text = _run_claude(body, timeout=240)
    return text or f"- _Synthesis returned empty for '{topic}'; raw evidence saved._"


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def _enabled_streams(streams: dict) -> dict:
    return {k: v for k, v in streams.items() if v.get("enabled")}


def _topic_streams() -> dict:
    """Map each configured topic -> its stream label (for KPI category breakdown)."""
    return {t: st.get("label", name)
            for name, st in load_topics().items() for t in st.get("topics", [])}


def research(py: str, env: dict, topic: str, sources: list[str], raw_dir: Path) -> str:
    """Plan (via Claude) + run the engine for one topic. Returns the raw markdown."""
    plan_path = generate_plan(topic, sources, raw_dir)
    return run_engine(py, env, topic, sources, raw_dir, plan_path)


def cmd_run(args) -> int:
    streams = _enabled_streams(load_topics())
    if not streams:
        sys.exit("No enabled streams in config/topics.yaml.")
    import time

    import metrics  # local import keeps deps lazy

    py, env = resolve_python(), engine_env()
    sources = available_sources(py, env)
    print(f"Keyless sources active: {', '.join(sources)}")
    today = _dt.date.today().isoformat()
    raw_dir = RAW / today
    started = time.time()
    sections = []
    src_inter: dict[str, int] = {}
    yt_reach = 0
    pts_idx: dict[str, int] = {}
    sources_seen: set[str] = set()
    for name, stream in streams.items():
        for topic in stream["topics"]:
            print(f"  - researching: {topic}")
            raw_md = research(py, env, topic, sources, raw_dir)
            synthesis = synthesize(topic, raw_md)
            score = _relevance_score(raw_md)
            # Sidecar synthesis so digests can be re-rendered without re-research.
            (raw_dir / f"{_slug(topic)}-synthesis.md").write_text(synthesis, encoding="utf-8")
            per_src, reach = metrics.source_breakdown(raw_md)
            for k, v in per_src.items():
                src_inter[k] = src_inter.get(k, 0) + v
            yt_reach += reach
            sources_seen |= metrics.sources_present(raw_md)
            pts_idx.update(points_index(raw_md))
            sections.append(
                {"topic": topic, "stream": stream["label"], "md": synthesis, "score": score}
            )
    # Most relevant first: read top-to-bottom in descending engagement order.
    sections.sort(key=lambda s: s["score"], reverse=True)
    from render_digest import render  # local import keeps deps lazy
    tag = getattr(args, "tag", None)
    out = DIGESTS / (f"{today}-{tag}.html" if tag else f"{today}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    rendered = render(today, sections, sources, pts_idx)
    out.write_text(rendered, encoding="utf-8")
    print(f"\nDigest written: {out}")

    # Cheap 3-judge quality scorer (Relevance / Faithfulness / Actionability).
    quality = None
    if not getattr(args, "no_judge", False):
        import judge  # local import keeps deps lazy
        print("  - judging digest quality (3 cheap judges)...")
        quality = judge.judge_run(today)
        if quality:
            print(f"    quality: composite={quality.get('composite')} "
                  f"(rel={quality.get('relevance')} faith={quality.get('faithfulness')} "
                  f"act={quality.get('actionability')})")

    # KPI metrics + executive dashboard.
    metrics.record_run(
        date=today, tag=tag or "",
        per_topic={s["topic"]: s["score"] for s in sections},
        sources=sources,
        bullets=rendered.count("<li>"), citations=rendered.count("<a href"),
        source_interactions=src_inter or None, youtube_reach=yt_reach or None,
        duration_s=time.time() - started,
        sources_with_data=sorted(sources_seen),
        quality=quality,
    )
    dash = metrics.render_dashboard(
        topic_streams=_topic_streams(),
        watchlist=metrics.extract_watchlist(rendered),
        anthropic=metrics.extract_section(rendered),
    )
    print(f"KPI dashboard updated: {dash}")
    return 0


def cmd_validate(args) -> int:
    """Run the engine on a few known topics and print RAW output for QE review."""
    if args.topics:
        topics = [t.strip() for t in args.topics.split(";") if t.strip()]
    else:
        streams = load_topics()
        ai = streams.get("ai", {})
        topics = ai.get("topics", [])[:3]
    py, env = resolve_python(), engine_env()
    sources = available_sources(py, env)
    print(f"=== VALIDATE — keyless sources: {', '.join(sources)} ===\n")
    raw_dir = RAW / "_validate"
    for topic in topics:
        print(f"\n{'='*70}\nTOPIC: {topic}\n{'='*70}")
        print(research(py, env, topic, sources, raw_dir))
    print("\n=== End of raw output. Judge relevance/recency before trusting digests. ===")
    return 0


def cmd_doctor(args) -> int:
    print("Daily Research Loop - preflight\n")
    py = resolve_python()
    pyver = subprocess.run([py, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"  [ok] engine python   : {py} ({pyver})")
    print(f"  [{'ok' if ENGINE_SCRIPT.exists() else '!!'}] engine script   : {ENGINE_SCRIPT}")
    gh = shutil.which("gh") or (os.path.join(GH_DIR, "gh.exe") if os.path.isdir(GH_DIR) else None)
    print(f"  [{'ok' if gh else '--'}] gh cli          : {gh or 'not found (GitHub source disabled)'}")
    claude = shutil.which("claude")
    print(f"  [{'ok' if claude else '!!'}] claude cli      : {claude or 'NOT FOUND (synthesis disabled)'}")
    env = engine_env()
    print(f"  [ok] keyless sources  : {', '.join(available_sources(py, env))}")
    print(f"  [ok] config           : {CONFIG} ({'exists' if CONFIG.exists() else 'MISSING'})")
    return 0


def cmd_kpi(args) -> int:
    """Rebuild the KPI dashboard; --backfill seeds the store from existing digests."""
    import metrics

    if args.backfill:
        n = metrics.backfill_from_digests(DIGESTS)
        print(f"Backfilled {n} digest(s) into the KPI store.")
    # Watch/read list comes from the latest run's digest file.
    rows = metrics.load_all()
    watchlist = anthropic = None
    if rows:
        latest = max(rows, key=lambda r: (r["date"], r.get("tag", ""), r.get("ts", "")))
        fn = f"{latest['date']}{('-' + latest['tag']) if latest.get('tag') else ''}.html"
        digest = DIGESTS / fn
        if digest.exists():
            _dh = digest.read_text(encoding="utf-8")
            watchlist = metrics.extract_watchlist(_dh)
            anthropic = metrics.extract_section(_dh)
    dash = metrics.render_dashboard(topic_streams=_topic_streams(), watchlist=watchlist, anthropic=anthropic)
    print(f"KPI store: {len(rows)} run(s). Dashboard: {dash}")
    return 0


_SECTION_RE = re.compile(r'<div class="stream">(.*?)</div><h2>(.*?)</h2>\s*(<ul>.*?</ul>)', re.DOTALL)
_LI_INNER_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)
_SCORE_BADGE_RE = re.compile(r"([\d,]+)\s*pts</span>")
_META_SOURCES_RE = re.compile(r"keyless sources:\s*(.*?)\s*·")


def _li_to_md(li: str) -> str:
    """Invert a rendered <li> back to markdown so the current renderer can re-emit it."""
    s = re.sub(r'<a href="(.*?)">(.*?)</a>', r"[\2](\1)", li, flags=re.DOTALL)
    s = re.sub(r'<span class="v-[a-z]+">(.*?)</span>', r"\1", s, flags=re.DOTALL)  # drop verdict color
    s = re.sub(r"<strong>(.*?)</strong>", r"**\1**", s, flags=re.DOTALL)
    s = re.sub(r"<em>(.*?)</em>", r"_\1_", s, flags=re.DOTALL)
    import html as _html
    return "- " + _html.unescape(s).strip()


def rerender_digest(path: Path) -> int:
    """Re-render an existing digest with the current renderer (no re-research)."""
    from render_digest import render

    h = path.read_text(encoding="utf-8")
    m = _META_SOURCES_RE.search(h)
    sources = ([s.strip() for s in m.group(1).split(",")]
               if m else ["reddit", "hackernews", "polymarket", "github", "youtube"])
    date = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem).group(1)
    raw_dir = RAW / date
    sections = []
    pts_idx: dict[str, int] = {}
    for badge, topic, ul in _SECTION_RE.findall(h):
        sc = _SCORE_BADGE_RE.search(badge)
        score = int(sc.group(1).replace(",", "")) if sc else 0
        label = badge.split("<span")[0].rstrip().rstrip("·").rstrip()
        md = "\n".join(_li_to_md(li) for li in _LI_INNER_RE.findall(ul))
        sections.append({"topic": topic, "stream": label, "md": md, "score": score})
        raw_file = raw_dir / f"{_slug(topic)}-raw.md"
        if raw_file.exists():  # per-bullet points only when raw is still on disk
            pts_idx.update(points_index(raw_file.read_text(encoding="utf-8")))
    sections.sort(key=lambda s: s["score"], reverse=True)
    path.write_text(render(date, sections, sources, pts_idx), encoding="utf-8")
    return len(sections)


def cmd_rerender(args) -> int:
    """Re-render all digests in place with the current renderer (e.g. after a style change)."""
    for f in sorted(DIGESTS.glob("*.html")):
        print(f"  re-rendered {f.name}: {rerender_digest(f)} sections")
    return 0


def cmd_judge(args) -> int:
    """Re-score a date's digest with the 3-judge panel and refresh the dashboard."""
    import judge
    import metrics

    date = args.date or _dt.date.today().isoformat()
    print(f"Judging {date} with 3 cheap judges (Relevance / Faithfulness / Actionability)...")
    quality = judge.judge_run(date)
    if not quality:
        sys.exit(f"No digest/raw data to judge for {date} (run it first).")
    metrics.attach_quality(date, args.tag or "", quality)
    rows = metrics.load_all()
    watchlist = anthropic = None
    if rows:
        latest = max(rows, key=lambda r: (r["date"], r.get("tag", ""), r.get("ts", "")))
        fn = f"{latest['date']}{('-' + latest['tag']) if latest.get('tag') else ''}.html"
        digest = DIGESTS / fn
        if digest.exists():
            _dh = digest.read_text(encoding="utf-8")
            watchlist = metrics.extract_watchlist(_dh)
            anthropic = metrics.extract_section(_dh)
    dash = metrics.render_dashboard(topic_streams=_topic_streams(), watchlist=watchlist, anthropic=anthropic)
    print(f"composite={quality.get('composite')}  rel={quality.get('relevance')}  "
          f"faith={quality.get('faithfulness')}  act={quality.get('actionability')}")
    if quality.get("issues"):
        print("issues:", json.dumps(quality["issues"])[:700])
    print(f"Dashboard updated: {dash}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Daily Research Loop orchestrator (keyless).")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Research enabled streams and write today's digest.")
    r.add_argument("--tag", help="Filename suffix for the digest (e.g. v2 -> 2026-06-15-v2.html).")
    r.add_argument("--no-judge", action="store_true", help="Skip the 3-judge quality scorer.")
    v = sub.add_parser("validate", help="Print RAW engine output for known topics (no synthesis).")
    v.add_argument("--topics", help="Semicolon-separated topics to validate.")
    sub.add_parser("doctor", help="Check prerequisites and active keyless sources.")
    k = sub.add_parser("kpi", help="Rebuild the KPI dashboard from the metrics store.")
    k.add_argument("--backfill", action="store_true", help="Seed the store from existing digests first.")
    sub.add_parser("rerender", help="Re-render all digests in place with the current renderer.")
    j = sub.add_parser("judge", help="Re-score a date's digest quality (3 cheap judges).")
    j.add_argument("--date", help="Date to judge (YYYY-MM-DD; default today).")
    j.add_argument("--tag", help="Digest tag, if any.")
    args = p.parse_args()
    return {
        "run": cmd_run, "validate": cmd_validate, "doctor": cmd_doctor,
        "kpi": cmd_kpi, "rerender": cmd_rerender, "judge": cmd_judge,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
