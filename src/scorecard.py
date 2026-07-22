"""Scorecard research — the `scorecard` command's engine + synthesis.

Turn a subjective "return me the best <X>" into an explicit, defensible answer:
a WEIGHTED RUBRIC that defines what "best" means for the subject, then a graded,
ranked shortlist of the real candidates scored against it. Produces a 4-section brief:

    Scoring rubric · Graded shortlist · Close calls & tradeoffs · Adopt this

The lane is deliberately general (score any subject), but its first configured
subject is "LLM & Claude evaluation scorecards" — so the first run doubles as a
due-diligence report on the eval-scorecard landscape itself.

SECURITY: this module never weakens the keyless contract. Like duediligence.py it
only shells out to the vendored engine through `orchestrator.run_engine` (scrubbed
env + keyless allowlist) and passes keyless-only targeting hints (--subreddits /
--github-repo). The hints cannot unlock a non-keyless source.

Two grounding paths share this module (mirrors the tool-dd design):
  * Headless `scorecard` command: keyless engine evidence -> headless `claude` synthesis.
  * Skill path: the hosting agent WebSearches doc-grounded facts (the canonical repos
    live in docs, not community feeds) and passes them in as `web_md`; synthesis merges both.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime


# --------------------------------------------------------------------------
# config/scorecards.yaml reader (zero-dependency, flat comma-separated scalars)
# --------------------------------------------------------------------------
def load_scorecards(path: Path | None = None) -> list[dict]:
    """Parse config/scorecards.yaml -> [{name, criteria, weights, subreddits, github_repos}, ...].

    Same tiny, dependency-free shape as duediligence.load_tools: a top-level
    `scorecards:` list of blocks whose values are scalars (comma-separated where a
    list is wanted).
    """
    path = path or (orch.ROOT / "config" / "scorecards.yaml")
    cards: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `scorecards:`
            continue
        if text.startswith("- "):  # new block: `- name: "..."`
            cur = {}
            cards.append(cur)
            text = text[2:].strip()
        if cur is None:
            continue
        key, _, val = text.partition(":")
        if val:
            cur[key.strip()] = orch._scalar(val)
    return [c for c in cards if c.get("name")]


def _csv(val: str | None) -> list[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# Scorecard query plan (deterministic — reliable, no extra Claude call)
# --------------------------------------------------------------------------
def scorecard_plan(subject: str, sources: list[str], raw_dir: Path) -> Path:
    """Write a scorecard-shaped query plan: find candidates + how "best" is defined.

    Returns the plan file path. Deterministic so a scheduled run never depends on a
    planner LLM being reachable. GitHub is foregrounded (candidate tools/templates and
    reference rubrics live in repos); a final subquery captures community verdict.
    """
    gh_first = [s for s in ("github", *sources) if s in sources]  # github first, deduped below
    seen: set[str] = set()
    gh_first = [s for s in gh_first if not (s in seen or seen.add(s))]
    plan = {
        "intent": "comparison",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "debate",
        "subqueries": [
            {
                "label": "templates",
                "search_query": f"{subject} scorecard rubric evaluation template",
                "ranking_query": (
                    f"What open-source scorecards, rubric templates, or evaluation frameworks "
                    f"exist for grading or ranking {subject}, and how are they structured?"
                ),
                "sources": gh_first,
                "weight": 1.0,
            },
            {
                "label": "candidates",
                "search_query": f"{subject} best comparison alternatives",
                "ranking_query": f"What are the top candidates/options for {subject} that people actually compare?",
                "sources": gh_first,
                "weight": 0.9,
            },
            {
                "label": "criteria",
                "search_query": f"{subject} criteria metrics how to evaluate choose",
                "ranking_query": f"How do practitioners define and weight what 'best' means for {subject}?",
                "sources": sources,
                "weight": 0.8,
            },
            {
                "label": "sentiment",
                "search_query": f"{subject} review worth it recommend production",
                "ranking_query": f"What does the community actually say about the best options for {subject}?",
                "sources": sources,
                "weight": 0.6,
            },
        ],
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{orch._slug(subject)}-scorecard-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def research_scorecard(py: str, env: dict, subject: str, sources: list[str],
                       raw_dir: Path, hints: dict | None = None) -> str:
    """Run the keyless engine for one subject with a scorecard plan + keyless hints."""
    hints = hints or {}
    plan_path = scorecard_plan(subject, sources, raw_dir)
    extra: list[str] = []
    subs = _csv(hints.get("subreddits"))
    repos = _csv(hints.get("github_repos"))
    if subs:
        extra += ["--subreddits", ",".join(subs)]
    if repos and "github" in sources:
        extra += ["--github-repo", ",".join(repos)]
    return orch.run_engine(py, env, subject, sources, raw_dir, plan_path, extra_args=extra)


# --------------------------------------------------------------------------
# 4-section synthesis
# --------------------------------------------------------------------------
_SCORECARD_SECTIONS = ("Scoring rubric", "Graded shortlist",
                       "Close calls & tradeoffs", "Adopt this")

_SCORECARD_SYNTH_INSTRUCTION = (
    "You are building a decision SCORECARD from 30-day research evidence (Reddit, Hacker News, "
    "GitHub, YouTube) and optional doc-grounded web notes. The user wants 'the best' for the "
    "SUBJECT, but 'best' is subjective — so make the definition explicit, then rank against it. "
    "Output GitHub-flavored markdown with EXACTLY this shape and nothing else:\n"
    "First line: '_Verdict:_ **<Adopt|Adapt|Hold>** - <best pick + 3-8 word reason>'.\n"
    "Then four sections, each a '## ' header in this exact order: "
    "'## Scoring rubric', '## Graded shortlist', '## Close calls & tradeoffs', '## Adopt this'.\n"
    "## Scoring rubric = 4-7 weighted criteria that DEFINE 'best' for this subject, one bullet each: "
    "'- **<Criterion>** (weight 0.NN) - <what earns a high score> [<source>](<url>)'. Weights are "
    "decimals that sum to ~1.0 and are a starting point the reader can re-weight (say so). Do NOT use "
    "a markdown table — the brief renderer only shows bullet lines. Ground each criterion in the "
    "evidence where possible (cite the source that argues the criterion matters).\n"
    "## Graded shortlist = the real candidates found, ranked best-first. One '- **<candidate>** "
    "(score /5) - <one-line why it ranks here>' bullet each, 3-6 candidates. Every candidate bullet "
    "MUST end with at least one inline markdown link copied VERBATIM from a URL in the evidence.\n"
    "## Close calls & tradeoffs = 2-4 bullets naming where the ranking flips if you re-weight, and "
    "which subjective calls drive it — make the subjectivity explicit, don't hide it.\n"
    "## Adopt this = the single recommendation + the reusable rubric to keep (2-4 bullets), each "
    "cited where it makes a factual claim.\n"
    "CITATION RULE: every bullet that makes a factual claim ends with a verbatim [name](url) link "
    "from the evidence; never invent a URL. THIN-EVIDENCE RULE: if a section has no grounding in the "
    "evidence, write one bullet stating that plainly rather than inventing candidates or scores."
)


def synthesize_scorecard(subject: str, raw_md: str, web_md: str = "") -> str:
    """Turn evidence (+ optional web notes) into the 4-section scorecard via headless Claude."""
    import shutil
    if not shutil.which("claude"):
        return (f"_Verdict:_ **Hold** - synthesis skipped, `claude` CLI not found\n\n"
                "## Scoring rubric\n- _Synthesis skipped: `claude` CLI not on PATH. Raw evidence saved._\n")
    web_block = f"\n\nWEB NOTES (doc-grounded, trust as authoritative):\n{web_md}" if web_md.strip() else ""
    body = f"{_SCORECARD_SYNTH_INSTRUCTION}\n\nSUBJECT: {subject}\n\nEVIDENCE:\n{raw_md}{web_block}"
    text = orch._run_claude(body, timeout=300)
    return text or f"_Verdict:_ **Hold** - synthesis returned empty for {subject}\n"
