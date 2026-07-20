"""Agent due-diligence research — the `agentdd` command's engine + synthesis.

Given a named Claude agent (a subagent / plugin / SDK agent), answer: what does
it do and when do you invoke it, how do you define or install it, what are the
gotchas and costs, and how mature is it + what does the community say? Produces a
4-section brief:

    What it does & when to invoke · How to define or install ·
    Gotchas & cost · Maturity & sentiment

This is the agent-native sibling of `duediligence.py` (the tool `dd` lane). Tools
get an "Integration map / MCP / SDK" framing; agents get a "what/when/define/cost"
framing. Both share the keyless engine and the same brief renderer.

SECURITY: this module never weakens the keyless contract. It only shells out to
the vendored engine through `orchestrator.run_engine` (scrubbed env + keyless
allowlist) and passes keyless-only targeting hints (--subreddits / --github-repo).
The hints cannot unlock a non-keyless source.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime


# --------------------------------------------------------------------------
# config/agents.yaml reader (zero-dependency, flat comma-separated scalars)
# --------------------------------------------------------------------------
def load_agents(path: Path | None = None) -> list[dict]:
    """Parse config/agents.yaml -> [{name, aliases, subreddits, github_repos}, ...].

    Same flat schema as duediligence.load_tools, but the top-level key is
    `agents:` instead of `tools:`. Kept dependency-free to match the rest of
    the repo's tiny YAML readers.
    """
    path = path or (orch.ROOT / "config" / "agents.yaml")
    agents: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if indent == 0:  # `agents:`
            continue
        if text.startswith("- "):  # new agent block: `- name: "..."`
            cur = {}
            agents.append(cur)
            text = text[2:].strip()
        if cur is None:
            continue
        key, _, val = text.partition(":")
        if val:
            cur[key.strip()] = orch._scalar(val)
    return [a for a in agents if a.get("name")]


def _csv(val: str | None) -> list[str]:
    return [p.strip() for p in (val or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# Agent due-diligence query plan (deterministic — no extra Claude call)
# --------------------------------------------------------------------------
def agentdd_plan(agent: str, sources: list[str], raw_dir: Path) -> Path:
    """Write an agent-shaped query plan: capability / install / cost / sentiment.

    Returns the plan file path. Deterministic so a scheduled run never depends
    on a planner LLM being reachable. GitHub is foregrounded (agent definitions,
    frontmatter, and plugins live in repos); a final subquery captures sentiment.
    """
    gh_first = [s for s in ("github", *sources) if s in sources]  # github first
    seen: set[str] = set()
    gh_first = [s for s in gh_first if not (s in seen or seen.add(s))]
    plan = {
        "intent": "product",
        "freshness_mode": "balanced_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": "capability",
                "search_query": f"{agent} agent what it does tools when to use",
                "ranking_query": (
                    f"What does the {agent} do, what tools and model does it get, "
                    f"and when should you invoke it?"
                ),
                "sources": gh_first,
                "weight": 1.0,
            },
            {
                "label": "install",
                "search_query": f"{agent} define install .claude/agents frontmatter plugin marketplace SDK",
                "ranking_query": (
                    f"How do you define or install the {agent} — file frontmatter under "
                    f".claude/agents, a plugin/marketplace, or the SDK agents config?"
                ),
                "sources": gh_first,
                "weight": 0.9,
            },
            {
                "label": "cost",
                "search_query": f"{agent} agent limitations context cost model isolation issues",
                "ranking_query": (
                    f"What are the known gotchas, context/token costs, model/effort, and "
                    f"limitations of the {agent}?"
                ),
                "sources": sources,
                "weight": 0.7,
            },
            {
                "label": "sentiment",
                "search_query": f"{agent} agent review experience worth it",
                "ranking_query": f"What does the community actually say about using the {agent} in real workflows?",
                "sources": sources,
                "weight": 0.6,
            },
        ],
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{orch._slug(agent)}-agentdd-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def research_agent(py: str, env: dict, agent: str, sources: list[str],
                   raw_dir: Path, hints: dict | None = None) -> str:
    """Run the keyless engine for one agent with an agent-DD plan + keyless hints."""
    hints = hints or {}
    plan_path = agentdd_plan(agent, sources, raw_dir)
    extra: list[str] = []
    subs = _csv(hints.get("subreddits"))
    repos = _csv(hints.get("github_repos"))
    if subs:
        extra += ["--subreddits", ",".join(subs)]
    if repos and "github" in sources:
        extra += ["--github-repo", ",".join(repos)]
    return orch.run_engine(py, env, agent, sources, raw_dir, plan_path, extra_args=extra)


# --------------------------------------------------------------------------
# 4-section synthesis
# --------------------------------------------------------------------------
_AGENTDD_SECTIONS = ("What it does & when to invoke", "How to define or install",
                     "Gotchas & cost", "Maturity & sentiment")

_AGENTDD_SYNTH_INSTRUCTION = (
    "You are writing an AGENT DUE-DILIGENCE brief from 30-day research evidence (Reddit, Hacker "
    "News, GitHub, YouTube) and optional doc-grounded web notes. The subject is a Claude agent "
    "(a subagent, plugin, or SDK agent). Decide whether a team should ADD this agent to their "
    "setup. Output GitHub-flavored markdown with EXACTLY this shape and nothing else:\n"
    "First line: '_Act or ignore:_ **<Act|Watch|Ignore>** - <3-8 word reason>'.\n"
    "Then four sections, each a '## ' header in this exact order: "
    "'## What it does & when to invoke', '## How to define or install', "
    "'## Gotchas & cost', '## Maturity & sentiment'. Under each header, 2-5 markdown bullets. "
    "Each bullet: '- **<lead-in>** - <detail> [<source>](<url>)'. Every bullet that makes a "
    "factual claim MUST end with at least one inline markdown link copied VERBATIM from a URL in "
    "the evidence; never invent a URL. "
    "What it does & when to invoke = purpose, the tools/model it gets, and the trigger conditions "
    "for invoking it. How to define or install = the concrete mechanism (`.claude/agents/*.md` "
    "frontmatter, a plugin/marketplace, or the SDK `agents` config) and any wiring steps. "
    "Gotchas & cost = context/token cost, model+effort, isolation, cold-start, and limitations. "
    "Maturity & sentiment = adoption, version/changelog trajectory, and what the community says. "
    "THIN-EVIDENCE RULE: if a section has no grounding in the evidence, write one bullet stating "
    "that plainly (e.g. '- No install mechanism found in the engine evidence; check the official "
    "docs.') rather than inventing."
)


def synthesize_agentdd(agent: str, raw_md: str, web_md: str = "") -> str:
    """Turn evidence (+ optional web notes) into the 4-section brief via headless Claude."""
    import shutil
    if not shutil.which("claude"):
        return (f"_Act or ignore:_ **Watch** - synthesis skipped, `claude` CLI not found\n\n"
                "## What it does & when to invoke\n"
                "- _Synthesis skipped: `claude` CLI not on PATH. Raw evidence saved._\n")
    web_block = f"\n\nWEB NOTES (doc-grounded, trust as authoritative):\n{web_md}" if web_md.strip() else ""
    body = f"{_AGENTDD_SYNTH_INSTRUCTION}\n\nAGENT: {agent}\n\nEVIDENCE:\n{raw_md}{web_block}"
    text = orch._run_claude(body, timeout=300)
    return text or f"_Act or ignore:_ **Watch** - synthesis returned empty for {agent}\n"
