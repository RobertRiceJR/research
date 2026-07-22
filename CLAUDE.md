# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **keyless** daily research loop. It shells out to a vendored `last30days` engine to pull recent
social/web discussion (Reddit, Hacker News, Polymarket, GitHub, YouTube), synthesizes cited digests
and briefs with the headless `claude` CLI, grades them with a cheap Haiku judge panel, and tracks KPIs.
Pure stdlib, no pip install, no API keys, no cookies.

## Running commands

Always drive the tool through the repo-root **`run` wrapper** — never bare `python`. On this machine
bare `python` is Anaconda 3.10, which the engine **rejects** (it hard-requires Python 3.12+); `run.cmd`
resolves the Python 3.13 interpreter and forwards args to `src/orchestrator.py`.

```powershell
.\run doctor                      # prereqs + which keyless sources are live (run this first)
.\run validate                    # RAW engine output for the first 3 `ai` topics (no synthesis) — the QE hook
.\run validate --topics "a;b"     # RAW output for specific semicolon-separated topics
.\run run                         # full loop: research enabled streams -> digest -> KPIs -> judge -> dashboard
.\run run --no-judge              # skip the 3-judge scorer
.\run judge --date 2026-06-20     # re-score one day's digest and refresh the dashboard
.\run kpi --backfill              # rebuild dashboard, seeding the store from existing digests
.\run rerender                    # re-emit all digests with the current renderer (no re-research)
.\run dd "<tool>" | --all         # tool due-diligence brief   (config/tools.yaml)
.\run agentdd "<agent>" | --all   # Claude-agent due-diligence  (config/agents.yaml)
.\run scorecard "<subject>" | --all  # weighted rubric + ranked shortlist (config/scorecards.yaml)
.\run recipe "<dish>" | --all     # restaurant-at-home recipe brief (config/recipes.yaml)
.\run todo "<place>" | --all      # things-to-do brief (config/todo.yaml)
.\run export-letsgo               # export researched todo places to the Let's Go! activities.json contract
```

Any lane command takes `--engine-only` to print the raw keyless engine evidence and skip synthesis
(the hook the `skills/*/SKILL.md` wrappers call so a hosting agent can merge in WebSearch-grounded
facts). `todo` also takes `--no-open-data`.

**Verification:** there is no automated test suite. `.\run doctor` (prereqs) and `.\run validate` (raw
evidence for human QE judgment) are the verification hooks. For unattended runs use
`pwsh -File scripts\run-daily.ps1 run`.

## The keyless security contract (do not weaken without review)

This is the central invariant of the codebase. The loop may only ever reach the five keyless sources
in `KEYLESS_SOURCES` (`reddit, hackernews, polymarket, github, youtube`). It is enforced in **three
independent layers** in [src/orchestrator.py](src/orchestrator.py):

1. The `KEYLESS_SOURCES` allowlist — the only sources passed as `--search=`.
2. `engine_env()` returns a **scrubbed** subprocess environment: every key/cookie var in `BLOCKED_ENV`
   is stripped, so even if this machine later has X / Brave / OpenAI keys, the engine can't use them.
3. `EXCLUDE_SOURCES` bans the rest by name as belt-and-suspenders.

When touching engine invocation: never pass `--x-handle` / `--tiktok-*` / `--ig-*` / `--auto-resolve`,
and never import the engine's cookie/session modules (they are **deleted**, not disabled, in the
vendored fork). We only shell out to the engine's documented CLI.

**Keyed sources are opt-in and isolated.** `src/parks_keyed.py` (NPS, reads its own `NPS_API_KEY`, a
no-op when unset) is the one wired keyed source; it and `src/places_open.py` (keyless open data:
Wikivoyage / Wikipedia GeoSearch / OSM Overpass) do read-only network from `src/` and are kept entirely
away from `engine_env()` and the allowlist. [docs/keyed-sources/](docs/keyed-sources/) is a
documentation-only catalog (no keys live there) — consult it before wiring any new key, mirroring the
NPS isolation pattern.

## Architecture

**Vendored engine.** [engine/](engine/) is a pruned, keyless-only fork of `mvanhorn/last30days-skill`
(MIT — see [engine/VENDORED.md](engine/VENDORED.md)). It is pure stdlib and is invoked **only as a
subprocess** (`engine/last30days.py` CLI). Never import it.

**Orchestrator as hub.** [src/orchestrator.py](src/orchestrator.py) is the single CLI entry point and
the home of every shared primitive: Python/source resolution, `engine_env()`, `run_engine()`,
`generate_plan()`, the headless-Claude bridge `_run_claude()`, engagement/points parsing, and the
zero-dependency YAML reader (`load_topics`, `_scalar`). Sibling modules `import orchestrator as orch`
(src/ is on `sys.path` at runtime); most imports inside command functions are lazy to keep the common
path light.

**The lane pattern.** `dd`, `agentdd`, `scorecard`, `recipe`, and `todo` are five instances of one
pattern — learn one and you know all five. Each `src/<lane>.py` exposes:
- `load_<x>()` — parse `config/<x>.yaml` (a flat, comma-separated-scalar list; same tiny reader shape).
- `research_<x>()` — build a query plan, add keyless targeting hints (`--subreddits` / `--github-repo`),
  and call `orch.run_engine(...)`. Hints only sharpen retrieval; they cannot unlock a non-keyless source.
- `synthesize_<x>()` — send evidence to `orch._run_claude(...)` with a strict section/citation
  instruction, returning section markdown.

The config files are **plug-and-play**: add a `- name:` block to `config/<x>.yaml`, run the command —
no code change. To add a new lane, clone an existing `src/<lane>.py`, add a `cmd_<lane>` + subparser in
the orchestrator, and add its entry to the dispatch dict in `main()`.

**Grounding, two paths.** Every lane runs either (a) fully headless — keyless engine evidence →
headless `claude` synthesis, no LLM API key ("the hosting reasoning model is the planner"); or (b) via
a `skills/*/SKILL.md` wrapper that adds WebSearch-grounded facts and passes them in as `web_md`, which
synthesis merges.

**Render / re-render.** [src/render_digest.py](src/render_digest.py) emits self-contained dark-mode HTML
(inline CSS, no external assets) via `render()` (daily digest) and `render_brief()` (lane briefs), with
color-coded Act/Watch/Ignore verdicts. Synthesis is saved as a sidecar `.md` under `raw/<date>/`, so
`rerender` can rebuild HTML from existing digests **without re-researching** (it inverts each `<li>`
back to markdown). Digests are sorted most-relevant-first by summed community engagement.

**KPIs & quality.** [src/metrics.py](src/metrics.py) appends one record per run to
`metrics/kpi.jsonl` (the tracked, cumulative source of truth) and regenerates `metrics/dashboard.html`
(inline SVG, no chart library). [src/judge.py](src/judge.py) runs three cheap **Haiku** judges per run
(Relevance / Faithfulness / Actionability); faithfulness is weighted highest (0.4) as the anti-fabricated-
citation trust gate, and a red banner fires on the dashboard if it drops below 70.

## Generated vs. tracked files

Regenerated and **gitignored**: `raw/`, `logs/`, `exports/`, `digests/*.html`, `briefs/*.html`,
`metrics/dashboard.html`, `plans/`. The one generated artifact that **is** tracked is
`metrics/kpi.jsonl` — it's the cumulative history the dashboard rebuilds from, so preserve it.
`reports/` holds hand-authored standing strategy briefs (tracked).

## Conventions

- **Stay dependency-free.** v0 is intentionally stdlib-only so a fresh or scheduled run is never held up
  by pip. Don't add a package or a real YAML lib; extend the tiny built-in reader instead.
- **Windows/UTF-8.** The engine emits UTF-8 (emoji trees); the orchestrator reconfigures stdout/stderr
  to UTF-8 and passes heavy prompts to `claude` via **stdin** (short ASCII directive in `-p`) to dodge
  cmd.exe quoting. Preserve that split when changing Claude calls.
- **Enrichment is best-effort** and must never block a brief — open-data / NPS fetches are wrapped so a
  miss degrades gracefully (the public Overpass instance in particular often 504s).
