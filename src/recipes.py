"""Recipe research — the `recipe` command's engine + (optional) synthesis.

Given a named dish, harvest what home cooks actually say recreates the
restaurant version at home: the best recipe/version, the technique that makes
or breaks it, and the common mistakes. Produces raw, engagement-ranked keyless
evidence (Reddit + YouTube are the useful sources here) that seeds the recipe
note's "Notes & Tweaks" section in the 5_Year_Plan vault.

This is the cooking sibling of `agentdd.py` / `duediligence.py`. Same keyless
engine, same deterministic-plan pattern, same brief renderer — only the query
framing changes (restaurant-at-home / technique / mistakes / best-version).

SECURITY: this module never weakens the keyless contract. It only shells out to
the vendored engine through `orchestrator.run_engine` (scrubbed env + keyless
allowlist) and passes keyless-only targeting hints (--subreddits). The hints
cannot unlock a non-keyless source.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime


# --------------------------------------------------------------------------
# config/recipes.yaml reader (zero-dependency, flat comma-separated scalars)
# --------------------------------------------------------------------------
def load_recipes(path: Path | None = None) -> list[dict]:
    """Parse config/recipes.yaml -> [{name, cuisine, protein, subreddits}, ...].

    Same flat schema as agentdd.load_agents, but the top-level key is
    `recipes:`. Kept dependency-free to match the rest of the repo's tiny
    YAML readers.
    """
    path = path or (orch.ROOT / "config" / "recipes.yaml")
    recipes: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `recipes:`
            continue
        if text.startswith("- "):  # new recipe block: `- name: "..."`
            cur = {}
            recipes.append(cur)
            text = text[2:].strip()
        if cur is None:
            continue
        key, _, val = text.partition(":")
        if val:
            cur[key.strip()] = orch._scalar(val)
    return [r for r in recipes if r.get("name")]


def _csv(val: str | None) -> list[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# Recipe query plan (deterministic — no extra Claude call)
# --------------------------------------------------------------------------
def recipe_plan(dish: str, sources: list[str], raw_dir: Path) -> Path:
    """Write a recipe-shaped query plan: restaurant-at-home / technique /
    mistakes / best-version.

    Returns the plan file path. Deterministic so a scheduled run never depends
    on a planner LLM being reachable. Reddit + YouTube are foregrounded (that's
    where home-cook consensus and technique demos live).
    """
    social_first = [s for s in ("reddit", "youtube", *sources) if s in sources]
    seen: set[str] = set()
    social_first = [s for s in social_first if not (s in seen or seen.add(s))]
    plan = {
        "intent": "howto",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": "restaurant_at_home",
                "search_query": f"{dish} restaurant quality at home best recipe",
                "ranking_query": (
                    f"Which {dish} recipe do home cooks say actually tastes like the "
                    f"restaurant version, using normal home ingredients and tools?"
                ),
                "sources": social_first,
                "weight": 1.0,
            },
            {
                "label": "technique",
                "search_query": f"{dish} technique tips how to get it right",
                "ranking_query": (
                    f"What is the key technique that makes or breaks {dish}, and how do "
                    f"you get restaurant results at home?"
                ),
                "sources": social_first,
                "weight": 0.9,
            },
            {
                "label": "mistakes",
                "search_query": f"{dish} common mistakes what people get wrong",
                "ranking_query": f"What are the common mistakes that ruin {dish}, and how do you avoid them?",
                "sources": social_first,
                "weight": 0.7,
            },
            {
                "label": "best_version",
                "search_query": f"{dish} best version reddit which recipe worth it",
                "ranking_query": f"Which specific {dish} recipe or method does the community rate highest and why?",
                "sources": social_first,
                "weight": 0.6,
            },
        ],
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{orch._slug(dish)}-recipe-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def research_recipe(py: str, env: dict, dish: str, sources: list[str],
                    raw_dir: Path, hints: dict | None = None) -> str:
    """Run the keyless engine for one dish with a recipe plan + keyless hints."""
    hints = hints or {}
    plan_path = recipe_plan(dish, sources, raw_dir)
    extra: list[str] = []
    subs = _csv(hints.get("subreddits"))
    if subs:
        extra += ["--subreddits", ",".join(subs)]
    return orch.run_engine(py, env, dish, sources, raw_dir, plan_path, extra_args=extra)


# --------------------------------------------------------------------------
# 3-section synthesis (optional — the raw harvest is already useful on its own)
# --------------------------------------------------------------------------
_RECIPE_SECTIONS = ("Restaurant-at-home verdict", "Technique that matters", "Common mistakes")

_RECIPE_SYNTH_INSTRUCTION = (
    "You are distilling 30-day home-cook research evidence (Reddit, YouTube) about ONE dish into "
    "practical notes for a home cook who wants restaurant-quality results without exotic tools or "
    "ingredients. Output GitHub-flavored markdown with EXACTLY this shape and nothing else:\n"
    "First line: '_Restaurant at home:_ **<Nails it|Close|Hard>** - <3-8 word reason>'.\n"
    "Then three sections, each a '## ' header in this exact order: "
    "'## Restaurant-at-home verdict', '## Technique that matters', '## Common mistakes'. "
    "Under each header, 2-5 markdown bullets. Each bullet: '- **<lead-in>** - <detail> [<source>](<url>)'. "
    "Every bullet that makes a factual claim MUST end with at least one inline markdown link copied "
    "VERBATIM from a URL in the evidence; never invent a URL. Prefer pantry-common ingredients and "
    "basic equipment; if a specialty item or tool keeps coming up, call it out and suggest a common "
    "substitute. THIN-EVIDENCE RULE: if a section has no grounding in the evidence, write one bullet "
    "stating that plainly rather than inventing."
)


def synthesize_recipe(dish: str, raw_md: str, web_md: str = "") -> str:
    """Turn evidence (+ optional web notes) into a 3-section recipe brief via headless Claude."""
    import shutil
    if not shutil.which("claude"):
        return (f"_Restaurant at home:_ **Close** - synthesis skipped, `claude` CLI not found\n\n"
                "## Restaurant-at-home verdict\n"
                "- _Synthesis skipped: `claude` CLI not on PATH. Raw evidence saved._\n")
    web_block = f"\n\nWEB NOTES (recipe-grounded, trust as authoritative):\n{web_md}" if web_md.strip() else ""
    body = f"{_RECIPE_SYNTH_INSTRUCTION}\n\nDISH: {dish}\n\nEVIDENCE:\n{raw_md}{web_block}"
    text = orch._run_claude(body, timeout=300)
    return text or f"_Restaurant at home:_ **Close** - synthesis returned empty for {dish}\n"
