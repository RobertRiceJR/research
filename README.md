.\run doctor
.\run run


# last30days Dashboard (Claude) — self-contained keyless research loop

A daily research loop that pulls what people are actually saying about your topics, synthesizes a
dark-mode digest, grades it with a cheap 3-judge quality panel, and tracks executive KPIs over time.

**Self-contained.** The research engine is **vendored in-repo** under [`engine/`](engine/) — a pruned,
**keyless-only** fork of [`mvanhorn/last30days-skill`](https://github.com/mvanhorn/last30days-skill)
(MIT). No external clone, no cookie/credential code (see [`engine/VENDORED.md`](engine/VENDORED.md)).

## Security model (keyless, no cookies)

- **Only 5 keyless sources:** Reddit, Hacker News, Polymarket, GitHub, YouTube. Nothing requiring an API
  key or browser cookies.
- The vendored engine has **all cookie-harvesting / X / TikTok / Instagram / session-auth modules
  deleted** — not just disabled. Triple-enforced at the orchestrator too: a `KEYLESS_SOURCES` allowlist,
  a **scrubbed subprocess env** (`engine_env()` strips every key/cookie var), and `EXCLUDE_SOURCES`.
- **Things-to-do open data** (`src/places_open.py`): the `todo` lane adds authoritative facts from three
  **keyless, GET-only, no-auth** open APIs (Wikivoyage · Wikipedia GeoSearch · OpenStreetMap/Overpass). This
  is read-only network from `src/` — separate from the engine, never near `engine_env()` or the allowlist —
  and best-effort (a miss degrades to social-only; the public Overpass instance in particular often 504s).
  Recreation.gov/RIDB was evaluated but needs a free key (HTTP 401 without one), so it is treated as a keyed
  opt-in, not keyless. `src/parks_keyed.py` is the **one wired opt-in keyed** source (NPS): it reads its own
  `NPS_API_KEY`, is a no-op when unset, and is likewise kept entirely away from the engine env.

## Layout

```
engine/        vendored keyless engine (last30days.py + lib/) · MIT · VENDORED.md
src/
  orchestrator.py   run / validate / doctor / kpi / rerender / judge
  render_digest.py  dark-mode digest (relevance sort, colored verdicts, per-bullet points)
  metrics.py        KPI store + dashboard (CFD, trends, breakdowns, watch list, quality)
  judge.py          3 cheap Haiku judges (Relevance / Faithfulness / Actionability)
  trending.py       Top-10 trending AI GitHub repos this week (keyless)
  duediligence.py   tool due-diligence: skill/MCP/integration brief per tool (dd command)
  agentdd.py        agent due-diligence: what/when/define/cost brief per Claude agent (agentdd command)
  recipes.py        recipe research: restaurant-at-home social proof per dish (recipe command)
  todo.py           things-to-do research: top / hidden gems / skip, per place (todo command)
  places_open.py    keyless open-data enrichment for todo (Wikivoyage/Wikipedia/OSM)
  parks_keyed.py    opt-in NPS enrichment for todo (the only keyed source; NPS_API_KEY)
config/topics.yaml  research streams + topics (incl. the claude_agents + travel discovery streams)
config/tools.yaml   tool due-diligence targets (plug-and-play: add a name, run `dd`)
config/agents.yaml  agent due-diligence targets (plug-and-play: add a name, run `agentdd`)
config/recipes.yaml recipe harvest targets (plug-and-play: add a dish, run `recipe`)
config/todo.yaml    things-to-do targets (plug-and-play: add a place, run `todo`)
skills/tool-dd/       portable SKILL.md wrapper (WebSearch-grounded tool due-diligence)
skills/things-to-do/  portable SKILL.md wrapper (WebSearch-grounded things-to-do)
reports/            standing strategy briefs (tracked; e.g. things-to-do data-avenues report)
digests/  briefs/  raw/  metrics/  (generated; gitignored except metrics/kpi.jsonl)
```

## Prerequisites (machine-verified)

| Tool | Notes |
| --- | --- |
| Python 3.12+ | `C:\Users\terri\AppData\Local\Programs\Python\Python313\python.exe`. Engine is pure stdlib. |
| `gh` CLI (authed) | gates the GitHub source; the loop injects its dir onto the engine PATH. |
| `yt-dlp` | keyless YouTube source (binary on PATH; the loop adds the Python Scripts dir). |
| `claude` CLI | headless query-planning, synthesis, and the Haiku judges. |

Run `python src\orchestrator.py doctor` to confirm.

## Commands

Use the **`run` wrapper** at the repo root — it resolves Python 3.13 (your bare `python` is Anaconda
3.10, which the engine rejects) and forwards args. From the repo root in PowerShell, prefix with `.\`:

```powershell
.\run doctor                 # prereqs + active keyless sources
.\run validate               # RAW engine output for QE judgment
.\run run                    # research -> digest -> KPIs -> judge -> dashboard
.\run run --no-judge         # skip the quality scorer
.\run judge --date 2026-06-20 # re-score a day's digest only
.\run kpi --backfill         # rebuild dashboard (seed from existing digests)
.\run rerender               # re-emit digests after a style change
.\run dd "Azure App Insights" # tool due-diligence -> briefs/<slug>-<date>.html
.\run dd --all               # due-diligence every tool in config/tools.yaml
.\run dd "<tool>" --engine-only # raw keyless evidence (hook for the tool-dd skill)
.\run agentdd "code-reviewer subagent" # agent due-diligence -> briefs/<slug>-<date>.html
.\run agentdd --all          # due-diligence every agent in config/agents.yaml
.\run agentdd "<agent>" --engine-only  # raw keyless evidence for one agent
.\run recipe "Chicken Piccata" # recipe research -> briefs/<slug>-<date>.html
.\run todo "Great Sand Dunes National Park" # things-to-do brief -> briefs/<slug>-<date>.html
.\run todo --all             # things-to-do brief for every place in config/todo.yaml
.\run todo "<place>" --engine-only   # raw keyless social evidence (hook for the things-to-do skill)
.\run todo "<place>" --no-open-data  # social evidence only (skip the open-data quartet)
```

**Things-to-do** (`todo`): the travel sibling of `recipe`. Given a place or
activity, it produces a 4-section brief — *Top things to do · Hidden gems & local
picks · Know before you go · Overrated / skip* — headed by a **Worth it: Act /
Watch / Ignore** verdict. It blends keyless social proof (Reddit, YouTube) with
authoritative **keyless open data** (Wikivoyage · Wikipedia GeoSearch ·
OpenStreetMap), and — only if `NPS_API_KEY` is set — an opt-in NPS section. The
`travel` discovery stream in [`config/topics.yaml`](config/topics.yaml) feeds it:
when the daily digest surfaces a place worth a full brief, add it to
[`config/todo.yaml`](config/todo.yaml) and run `todo`. For a richer,
WebSearch-grounded brief (TripAdvisor / Atlas Obscura / tourism boards), use the
[`skills/things-to-do`](skills/things-to-do/SKILL.md) wrapper. See the strategy
brief in [`reports/`](reports/) for the full source due-diligence.

**Agent due-diligence** (`agentdd`): the agent-native sibling of `dd`. Given a
Claude agent (subagent / plugin / SDK agent), it produces a 4-section brief —
*What it does & when to invoke · How to define or install · Gotchas & cost ·
Maturity & sentiment* — headed by an **Act / Watch / Ignore** verdict. The
`claude_agents` discovery stream in [`config/topics.yaml`](config/topics.yaml)
feeds it: when the daily digest surfaces an agent worth evaluating, add it to
[`config/agents.yaml`](config/agents.yaml) and run `agentdd` for the full brief.

**Tool due-diligence** (`dd`): given a tool name, research whether a drop-in
skill / MCP server / SDK exists, how to wire it, the gotchas + environment
prereqs, how mature it is, and what the community says — as a shareable 4-section
HTML brief. The baked-in command is keyless + autonomous; the portable
[`skills/tool-dd`](skills/tool-dd/SKILL.md) wrapper adds WebSearch-grounded
discovery for a materially richer Integration map.

> For unattended/scheduled runs use `pwsh -File scripts\run-daily.ps1 run` (resolves Python + gh, logs).

Each `run` writes `digests/YYYY-MM-DD.html`, appends a row to `metrics/kpi.jsonl`, and rebuilds
`metrics/dashboard.html`.

## The digest

Topics sorted **most-relevant-first** (by total engagement). Each bullet: *what changed / why it matters
/ verdict*, with the **verdict color-coded** (green Act · red Ignore · amber Watch) and the cited item's
**backing points** shown inline.

## The 3-judge quality scorer

After each run, three cheap **Haiku** judges score the whole digest (3 calls total):
- **Relevance** — on-topic and substantive vs. noise?
- **Faithfulness** — do cited links match the run's real evidence URLs (no fabricated citations)? *(the
  QE trust gate)*
- **Actionability** — are the verdicts sound and the takeaways useful?

Composite (faithfulness-weighted) lands on the dashboard as a **Digest quality** card + trend, and a
**red banner** fires if faithfulness drops below 70 (possible unsupported citations).

## Dashboard KPIs

Top to bottom:
- **Top-10 trending AI repos this week** — keyless scrape of `github.com/trending?since=weekly`
  (AI-filtered, star-velocity), refreshed on every dashboard rebuild.
- **Cumulative Flow Diagram** — cumulative interactions per **stream** as stacked bands over the last
  ~14 runs (2-week trend).
- **Interactions per run** (source-outage runs flagged ⚠), **stream trend**, and per-topic / per-stream
  **breakdowns** for the latest run.
- A sticky **Read / Watch list** (Act + Watch items, clickable) on the right.
- KPI cards: cumulative + latest interactions, **digest quality**, **source health** (an outage shows as
  ⚠, never a mysterious cliff), citations, YouTube reach.

Interactions = upvotes + points + reactions + comments (YouTube views tracked separately as reach).

## Scheduling

`scripts\run-daily.ps1` resolves Python + `gh` and runs the loop; register it with Windows Task
Scheduler for a daily cadence (see the script header).
