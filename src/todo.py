"""Things-to-do research — the `todo` command's engine + synthesis.

Given a place or activity, harvest what visitors actually say is worth doing there:
the top experiences, the hidden gems locals pick, the logistics that make or break
a visit, and what's overrated. Produces raw, engagement-ranked keyless evidence
(Reddit + YouTube are the useful sources here), optionally enriched with authoritative
keyless open-data notes (Wikivoyage / Wikipedia GeoSearch / OpenStreetMap) merged via
the `web_md` hook.

This is the travel sibling of `recipes.py` / `agentdd.py`. Same keyless engine, same
deterministic-plan pattern, same brief renderer — only the query framing changes
(top experiences / hidden gems / logistics / overrated).

SECURITY: this module never weakens the keyless contract. It only shells out to the
vendored engine through `orchestrator.run_engine` (scrubbed env + keyless allowlist)
and passes keyless-only targeting hints (--subreddits). The optional open-data
enrichment (see places_open.py) is keyless + GET-only and best-effort; the hints
cannot unlock a non-keyless source.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime


# --------------------------------------------------------------------------
# config/todo.yaml reader (zero-dependency, flat comma-separated scalars)
# --------------------------------------------------------------------------
def load_todo(path: Path | None = None) -> list[dict]:
    """Parse config/todo.yaml -> [{name, location, category, subreddits, lat, lon}, ...].

    Same flat schema as recipes.load_recipes / agentdd.load_agents, but the
    top-level key is `todo:`. Kept dependency-free to match the rest of the
    repo's tiny YAML readers.
    """
    path = path or (orch.ROOT / "config" / "todo.yaml")
    items: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `todo:`
            continue
        if text.startswith("- "):  # new place block: `- name: "..."`
            cur = {}
            items.append(cur)
            text = text[2:].strip()
        if cur is None:
            continue
        key, _, val = text.partition(":")
        if val:
            cur[key.strip()] = orch._scalar(val)
    return [t for t in items if t.get("name")]


def _csv(val: str | None) -> list[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# Things-to-do query plan (deterministic — no extra Claude call)
# --------------------------------------------------------------------------
def todo_plan(place: str, sources: list[str], raw_dir: Path) -> Path:
    """Write a things-to-do query plan: top experiences / hidden gems / logistics /
    overrated.

    Returns the plan file path. Deterministic so a scheduled run never depends on a
    planner LLM being reachable. Reddit + YouTube are foregrounded (that's where
    visitor consensus and walk-throughs live).
    """
    social_first = [s for s in ("reddit", "youtube", *sources) if s in sources]
    seen: set[str] = set()
    social_first = [s for s in social_first if not (s in seen or seen.add(s))]
    plan = {
        "intent": "opinion",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": "top_experiences",
                "search_query": f"{place} best things to do must see worth it",
                "ranking_query": (
                    f"What are the top things to do at {place} that visitors say are actually "
                    f"worth the time and money?"
                ),
                "sources": social_first,
                "weight": 1.0,
            },
            {
                "label": "hidden_gems",
                "search_query": f"{place} hidden gems local tips underrated off the beaten path",
                "ranking_query": (
                    f"What hidden gems or local favorites at {place} do people recommend over "
                    f"the obvious tourist spots?"
                ),
                "sources": social_first,
                "weight": 0.9,
            },
            {
                "label": "logistics",
                "search_query": f"{place} tips know before you go parking tickets timing cost crowds",
                "ranking_query": (
                    f"What do you need to know before visiting {place} — best timing, cost, "
                    f"parking, tickets, and crowds?"
                ),
                "sources": social_first,
                "weight": 0.7,
            },
            {
                "label": "overrated",
                "search_query": f"{place} overrated tourist trap skip not worth it",
                "ranking_query": f"What at {place} is overrated or a tourist trap that people say you can skip?",
                "sources": social_first,
                "weight": 0.6,
            },
        ],
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{orch._slug(place)}-todo-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def research_todo(py: str, env: dict, place: str, sources: list[str],
                  raw_dir: Path, hints: dict | None = None) -> str:
    """Run the keyless engine for one place with a things-to-do plan + keyless hints."""
    hints = hints or {}
    plan_path = todo_plan(place, sources, raw_dir)
    extra: list[str] = []
    subs = _csv(hints.get("subreddits"))
    if subs:
        extra += ["--subreddits", ",".join(subs)]
    return orch.run_engine(py, env, place, sources, raw_dir, plan_path, extra_args=extra)


# --------------------------------------------------------------------------
# 4-section synthesis (raw harvest + optional open-data notes)
# --------------------------------------------------------------------------
_TODO_SECTIONS = ("Top things to do", "Hidden gems & local picks",
                  "Know before you go", "Overrated / skip")

_TODO_SYNTH_INSTRUCTION = (
    "You are distilling 30-day traveler/visitor research evidence (Reddit, YouTube) plus optional "
    "authoritative open-data notes (Wikivoyage, Wikipedia, OpenStreetMap, and opt-in NPS) about "
    "ONE place or activity into a practical 'things to do' brief. Output GitHub-flavored markdown with "
    "EXACTLY this shape and nothing else:\n"
    "First line: '_Worth it:_ **<Act|Watch|Ignore>** - <3-8 word reason>' "
    "(Act = go, Watch = maybe / depends, Ignore = skip).\n"
    "Then four sections, each a '## ' header in this exact order: "
    "'## Top things to do', '## Hidden gems & local picks', '## Know before you go', "
    "'## Overrated / skip'. Under each header, 2-5 markdown bullets. Each bullet: "
    "'- **<lead-in>** - <detail> [<source>](<url>)'. Every bullet that makes a factual claim MUST end "
    "with at least one inline markdown link copied VERBATIM from a URL in the evidence or notes; never "
    "invent a URL. Prefer concrete, actionable picks over generic advice. 'Know before you go' = timing, "
    "cost, tickets, parking, crowds, seasonality. 'Overrated / skip' = what people say isn't worth it "
    "(or say so plainly if nothing stood out). THIN-EVIDENCE RULE: if a section has no grounding in the "
    "evidence, write one bullet stating that plainly rather than inventing."
)


def synthesize_todo(place: str, raw_md: str, web_md: str = "") -> str:
    """Turn evidence (+ optional open-data notes) into a 4-section brief via headless Claude."""
    import shutil
    if not shutil.which("claude"):
        return (f"_Worth it:_ **Watch** - synthesis skipped, `claude` CLI not found\n\n"
                "## Top things to do\n"
                "- _Synthesis skipped: `claude` CLI not on PATH. Raw evidence saved._\n")
    web_block = (f"\n\nOPEN-DATA & WEB NOTES (authoritative, trust and cite verbatim):\n{web_md}"
                 if web_md.strip() else "")
    body = f"{_TODO_SYNTH_INSTRUCTION}\n\nPLACE: {place}\n\nEVIDENCE:\n{raw_md}{web_block}"
    text = orch._run_claude(body, timeout=300)
    return text or f"_Worth it:_ **Watch** - synthesis returned empty for {place}\n"
