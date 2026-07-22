---
name: tool-dd
version: "0.1.0"
description: >-
  Tool due-diligence research. Given a named tool, find whether a drop-in skill /
  MCP server / SDK / CLI exists to integrate it with AI coding agents, how to wire
  it, the gotchas + environment prereqs, how mature it is, and what the community
  says. Produces a shareable HTML brief led by a skill-as-a-service availability
  scorecard (official skill? MCP? SDK? install path? maturity tier?). Use when the
  user asks "is there a skill/MCP/integration for <tool>", "do due-diligence on
  <tool>", or "research <tool> for my stack".
allowed-tools: WebSearch, Bash, Read, Write
---

# Tool Due-Diligence (`tool-dd`)

Plug in a tool name → get a brief that leads with a **skill-as-a-service availability scorecard**
(is there an official skill / MCP / SDK, and how mature?) followed by four detail sections:
**Availability scorecard · Integration map · Gotchas + environments · Historical record · References + sentiment.**

This skill has TWO grounding layers. Run BOTH for a full brief; the engine alone
misses doc-only facts (marketplaces, vendor docs, changelog), and WebSearch alone
misses what practitioners actually report.

## Step 0 — Load WebSearch

First tool call, every time:

```
ToolSearch select:WebSearch
```

## Step 1 — WebSearch the doc-grounded facts (the richest layer)

Run 3-4 searches to resolve the parts the keyless engine can't reach. Adapt the
queries to the tool, but cover these angles:

1. `"<tool> official MCP server skill plugin SDK claude code integration <year>"` — what drop-ins
   exist, and crucially **official vs third-party** (resolves the scorecard's first three fields)
2. `"<tool> setup prerequisites limitations gotchas"` — environment + gotchas
3. `"<tool> changelog release github issue onboarding GA beta"` — maturity (resolves the scorecard
   **Maturity** field: GA / Beta / Experimental / Community-only / None)
4. `"<tool> review experience site:reddit.com OR site:news.ycombinator.com"` — sentiment

Capture, for each finding: the claim + a VERBATIM source URL (docs, repo, marketplace,
blog). You will hand these to synthesis as authoritative "web notes". The scorecard is only as
honest as this step — a field with no source becomes **Unknown**, never a guess.

## Step 2 — Run the keyless engine for community + GitHub evidence

```bash
.\run dd "<tool>" --engine-only
```

This runs the vendored last30days engine (keyless: Reddit, HN, GitHub, YouTube) with
a due-diligence query plan, and prints the raw ranked evidence. It does NOT synthesize —
that's your job, so you can merge in the Step 1 web notes. If the tool is already in
`config/tools.yaml`, its `subreddits` / `github_repos` hints sharpen retrieval; if not,
add a block there first (plug-and-play) or just run the command ad-hoc.

## Step 3 — Synthesize the 4-section brief

Merge Step 1 (web notes, authoritative) + Step 2 (engine evidence, community signal)
into EXACTLY this markdown shape, then write it to the brief:

```
_Act or ignore:_ **<Act|Watch|Ignore>** - <3-8 word reason>

## Availability scorecard
- **Official skill** - Yes/No/Unknown (+ name) [<source>](<url>)
- **MCP server** - Yes/No/Unknown (+ official vs third-party, + repo) [<source>](<url>)
- **SDK / CLI** - Yes/No/Unknown (+ language/package) [<source>](<url>)
- **Install path** - one-line way to wire it into an agent [<source>](<url>)
- **Maturity** - GA / Beta / Experimental / Community-only / None [<source>](<url>)

## Integration map
- **<lead-in>** - available skills / MCP / SDK / CLI + how to wire it [<source>](<url>)

## Gotchas + environments
- **<lead-in>** - limitation or per-environment prereq [<source>](<url>)

## Historical record
- **<lead-in>** - maturity / changelog / onboarding status [<source>](<url>)

## References + sentiment
- **<lead-in>** - cited source + what the community says [<source>](<url>)
```

Rules: every factual bullet ends with a verbatim inline `[name](url)` link — never
invent a URL. Lead with official integrations, note third-party. If a section has no
grounding, say so plainly rather than padding. See the canonical example at
`raw/2026-06-22/azure-app-insights-mcp-skill-claude-code-observability-synthesis.md`.

## Step 4 — Render the shareable HTML brief

Save your synthesis markdown and render it with the repo's brief renderer:

```bash
python -c "import sys; sys.path.insert(0,'src'); from render_digest import render_brief; from pathlib import Path; md=Path('raw/<date>/<slug>-dd-synthesis.md').read_text(encoding='utf-8'); Path('briefs').mkdir(exist_ok=True); Path('briefs/<slug>-<date>.html').write_text(render_brief('<tool>', md, ['reddit','hackernews','github','youtube'], {'date':'<date>'}), encoding='utf-8')"
```

Confirm the path to the user. The brief is self-contained dark-mode HTML, shareable as-is.

## Headless alternative

For an autonomous (no-WebSearch) brief — scheduled runs, or when you just want the
community + GitHub picture — skip Steps 1/3/4 and run the baked-in command, which
synthesizes via headless Claude and writes the brief itself:

```bash
.\run dd "<tool>"          # one tool
.\run dd --all             # every tool in config/tools.yaml
```

This is honest about its limits: doc-only facts get a thin-evidence note. The
WebSearch path above is materially richer for the Integration map.
