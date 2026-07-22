"""Tool due-diligence research — the `dd` command's engine + synthesis.

Given a named tool, answer: does a drop-in skill / MCP server / SDK exist, how do
you wire it, what are the gotchas, how mature is it, and what does the community
say? Produces a 4-section brief:

    Integration map · Gotchas + environments · Historical record · References + sentiment

SECURITY: this module never weakens the keyless contract. It only shells out to
the vendored engine through `orchestrator.run_engine` (scrubbed env + keyless
allowlist) and passes keyless-only targeting hints (--subreddits / --github-repo).
The hints cannot unlock a non-keyless source.

Two grounding paths share this module (see plan):
  * Headless `dd` command: keyless engine evidence -> headless `claude` synthesis.
  * Skill path: the hosting agent WebSearches doc-grounded facts and passes them
    in as `web_md`; synthesis merges both.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime


# --------------------------------------------------------------------------
# config/tools.yaml reader (zero-dependency, flat comma-separated scalars)
# --------------------------------------------------------------------------
def load_tools(path: Path | None = None) -> list[dict]:
    """Parse config/tools.yaml -> [{name, aliases, subreddits, github_repos}, ...].

    Schema is a top-level `tools:` list of blocks whose values are scalars
    (comma-separated where a list is wanted). Kept deliberately flat so the
    parser stays tiny and dependency-free, like load_topics in orchestrator.
    """
    path = path or (orch.ROOT / "config" / "tools.yaml")
    tools: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `tools:`
            continue
        if text.startswith("- "):  # new tool block: `- name: "..."`
            cur = {}
            tools.append(cur)
            text = text[2:].strip()
        if cur is None:
            continue
        key, _, val = text.partition(":")
        if val:
            cur[key.strip()] = orch._scalar(val)
    return [t for t in tools if t.get("name")]


def _csv(val: str | None) -> list[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# Due-diligence query plan (deterministic — reliable, no extra Claude call)
# --------------------------------------------------------------------------
def dd_plan(tool: str, sources: list[str], raw_dir: Path) -> Path:
    """Write a DD-shaped query plan: integration/skill/MCP discovery + sentiment.

    Returns the plan file path. Deterministic so a scheduled run never depends
    on a planner LLM being reachable. GitHub is foregrounded (skills/MCP/SDKs
    live in repos); a final subquery captures community sentiment.
    """
    gh_first = [s for s in ("github", *sources) if s in sources]  # github first, deduped below
    seen: set[str] = set()
    gh_first = [s for s in gh_first if not (s in seen or seen.add(s))]
    plan = {
        "intent": "product",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": "integration",
                "search_query": f"{tool} official MCP server skill plugin extension SDK marketplace integration",
                "ranking_query": (
                    f"What drop-in skills, MCP servers, SDKs, or CLIs exist to integrate "
                    f"{tool} with AI coding agents — official vs third-party, and how mature "
                    f"are they (GA, beta, experimental)?"
                ),
                "sources": gh_first,
                "weight": 1.0,
            },
            {
                "label": "agent_wiring",
                "search_query": f"{tool} claude code copilot agent plugin setup",
                "ranking_query": f"How do developers connect {tool} into agent workflows like Claude Code or Copilot?",
                "sources": gh_first,
                "weight": 0.8,
            },
            {
                "label": "gotchas",
                "search_query": f"{tool} limitations gotchas setup prerequisites issues",
                "ranking_query": f"What are the known gotchas, limitations, and per-environment prerequisites for {tool}?",
                "sources": sources,
                "weight": 0.7,
            },
            {
                "label": "sentiment",
                "search_query": f"{tool} review experience worth it",
                "ranking_query": f"What does the community actually say about using {tool} in production?",
                "sources": sources,
                "weight": 0.6,
            },
        ],
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{orch._slug(tool)}-dd-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def research_tool(py: str, env: dict, tool: str, sources: list[str],
                  raw_dir: Path, hints: dict | None = None) -> str:
    """Run the keyless engine for one tool with a DD plan + keyless hints."""
    hints = hints or {}
    plan_path = dd_plan(tool, sources, raw_dir)
    extra: list[str] = []
    subs = _csv(hints.get("subreddits"))
    repos = _csv(hints.get("github_repos"))
    if subs:
        extra += ["--subreddits", ",".join(subs)]
    if repos and "github" in sources:
        extra += ["--github-repo", ",".join(repos)]
    return orch.run_engine(py, env, tool, sources, raw_dir, plan_path, extra_args=extra)


# --------------------------------------------------------------------------
# 4-section synthesis
# --------------------------------------------------------------------------
_DD_SECTIONS = ("Availability scorecard", "Integration map", "Gotchas + environments",
                "Historical record", "References + sentiment")

_DD_SYNTH_INSTRUCTION = (
    "You are writing a TOOL DUE-DILIGENCE brief from 30-day research evidence (Reddit, Hacker "
    "News, GitHub, YouTube) and optional doc-grounded web notes. The core question is "
    "SKILL-AS-A-SERVICE AVAILABILITY: is there a drop-in skill / MCP server / SDK / CLI to wire "
    "this tool into an AI coding agent, and how mature is it? Decide whether a team should adopt "
    "it. Output GitHub-flavored markdown with EXACTLY this shape and nothing else:\n"
    "First line: '_Act or ignore:_ **<Act|Watch|Ignore>** - <3-8 word reason>'.\n"
    "Then FIVE sections, each a '## ' header in this exact order: "
    "'## Availability scorecard', '## Integration map', '## Gotchas + environments', "
    "'## Historical record', '## References + sentiment'.\n"
    "AVAILABILITY SCORECARD comes FIRST — the at-a-glance answer. Emit EXACTLY these five "
    "bullets, in this order, each as '- **<field>** - <value> [<source>](<url>)':\n"
    "  - **Official skill** - Yes/No/Unknown (+ name) — a vendor-published agent/Claude Code skill\n"
    "  - **MCP server** - Yes/No/Unknown (+ official vs third-party, + repo)\n"
    "  - **SDK / CLI** - Yes/No/Unknown (+ language/package)\n"
    "  - **Install path** - the one-line way you'd actually wire it into an agent\n"
    "  - **Maturity** - exactly one of: GA / Beta / Experimental / Community-only / None\n"
    "For the other four sections, 2-5 markdown bullets each, '- **<lead-in>** - <detail> "
    "[<source>](<url>)'. Every bullet that makes a factual claim MUST end with at least one inline "
    "markdown link copied VERBATIM from a URL in the evidence; never invent a URL. Integration map "
    "= skills/MCP/SDKs/CLIs + how to wire them. Gotchas + environments = limitations + "
    "per-environment prerequisites. Historical record = maturity, changelog/version trajectory, "
    "onboarding/issue status. References + sentiment = cited sources + what the community says. "
    "THIN-EVIDENCE RULE: if a field or section has no grounding in the evidence, say so plainly "
    "(e.g. '- **MCP server** - Unknown: not found in the engine evidence; run the skill path for "
    "doc-grounded discovery.') rather than inventing — a scorecard field with no evidence is "
    "'Unknown', never a guessed Yes/No."
)


def synthesize_dd(tool: str, raw_md: str, web_md: str = "") -> str:
    """Turn evidence (+ optional web notes) into the 4-section brief via headless Claude."""
    import shutil
    if not shutil.which("claude"):
        return (f"_Act or ignore:_ **Watch** - synthesis skipped, `claude` CLI not found\n\n"
                "## Integration map\n- _Synthesis skipped: `claude` CLI not on PATH. Raw evidence saved._\n")
    web_block = f"\n\nWEB NOTES (doc-grounded, trust as authoritative):\n{web_md}" if web_md.strip() else ""
    body = f"{_DD_SYNTH_INSTRUCTION}\n\nTOOL: {tool}\n\nEVIDENCE:\n{raw_md}{web_block}"
    text = orch._run_claude(body, timeout=300)
    return text or f"_Act or ignore:_ **Watch** - synthesis returned empty for {tool}\n"
