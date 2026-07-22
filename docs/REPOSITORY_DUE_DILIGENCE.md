# Repository Due-Diligence — `last30daysDashboard_Claude`

> A technical account of what this repository is, how it runs, and how it is extended.
> Written as onboarding/handoff documentation. Last reviewed: 2026-06-22.

## 1. Purpose & provenance

A **keyless daily-research loop**. It pulls what people are actually saying about a configured set
of topics, synthesizes a dark-mode digest, grades that digest with a cheap 3-judge quality panel,
and tracks executive KPIs over time on a self-contained HTML dashboard.

The research engine is **vendored in-repo** under [`engine/`](../engine/) — a pruned, **keyless-only**
fork of [`mvanhorn/last30days-skill`](https://github.com/mvanhorn/last30days-skill) (MIT; see
[`engine/LICENSE`](../engine/LICENSE) and [`engine/VENDORED.md`](../engine/VENDORED.md)). The fork
deletes every cookie-harvesting / session-auth / non-keyless source module rather than disabling it.
Everything in [`src/`](../src/) is a homegrown, zero-dependency orchestrator wrapped around that engine.

## 2. Architecture

Two layers:

- **Orchestrator** (`src/`, pure Python stdlib) — owns the security contract, the CLI, config
  parsing, synthesis prompts, rendering, scoring, and metrics.
- **Vendored engine** (`engine/`) — does retrieval/ranking/clustering across the keyless sources and
  emits ranked markdown evidence. Invoked only through its documented CLI as a subprocess.

End-to-end data flow for one topic:

```
config/topics.yaml
  → orchestrator.cmd_run
    → research()            (optional headless `claude` query plan, then run_engine())
      → run_engine()        (subprocess to engine/last30days.py, SCRUBBED env, keyless allowlist)
        → raw ranked markdown evidence
    → synthesize()          (headless `claude` → 5-bullet markdown)
    → render_digest.render  (markdown → dark-mode HTML)  → digests/YYYY-MM-DD.html
    → judge.judge_run       (3 Haiku judges: relevance / faithfulness / actionability)
    → metrics.record_run    → metrics/kpi.jsonl  (append one row per run)
    → metrics.render_dashboard → metrics/dashboard.html
```

Source modules ([`src/`](../src/)):

| File | Role |
|---|---|
| `orchestrator.py` | Daily loop controller; CLI dispatch; security boundary; zero-dep YAML reader; `dd` command. |
| `duediligence.py` | Tool due-diligence engine + synthesis (the `dd` command's brains). |
| `render_digest.py` | Dark-mode HTML for the daily digest (`render`) and the `dd` brief (`render_brief`). |
| `judge.py` | 3 cheap Haiku judges; faithfulness-weighted composite; red banner < 70. |
| `metrics.py` | KPI store (`kpi.jsonl`) + dashboard renderer (CFD, trends, breakdowns, watch list). |
| `trending.py` | Top-10 trending AI GitHub repos this week (keyless scrape + Search-API fallback). |

## 3. How to run

Driven by the repo-root **`run.cmd`** wrapper — `.\run <command>` (resolves Python, forwards args):

| Command | What it does |
|---|---|
| `.\run doctor` | Verify prerequisites + report active keyless sources. |
| `.\run run` | Full loop: research → digest → KPIs → judge → dashboard. |
| `.\run run --no-judge` | Skip the quality scorer. |
| `.\run validate` | Print RAW engine output for QE judgment (no synthesis). |
| `.\run judge --date YYYY-MM-DD` | Re-score a single day's digest. |
| `.\run kpi --backfill` | Rebuild the dashboard, seeding from existing digests. |
| `.\run rerender` | Re-emit digests after a style change. |
| `.\run dd "<tool>"` | Tool due-diligence → `briefs/<slug>-<date>.html`. |
| `.\run dd --all` | Due-diligence every tool in `config/tools.yaml`. |
| `.\run dd "<tool>" --engine-only` | Raw keyless evidence only (the hook the `tool-dd` skill calls). |

Scheduled/unattended: `pwsh -File scripts\run-daily.ps1 run` (resolves Python + `gh`, logs to `logs/`).

**Outputs:** `digests/YYYY-MM-DD.html` (per run), `metrics/kpi.jsonl` (one row/run, the only tracked
output), `metrics/dashboard.html` (rebuilt each run), `briefs/<slug>-<date>.html` (from `dd`).
`digests/`, `raw/`, `briefs/`, `logs/` are gitignored.

## 4. Security contract (keyless, no cookies)

Only five keyless sources are ever reachable: **Reddit, Hacker News, Polymarket, GitHub, YouTube**.
Enforced at three independent levels in `orchestrator.py` (`orchestrator.py:40-58`, `:142-157`):

1. **`KEYLESS_SOURCES`** — the allowlist tuple; the engine is only ever asked for these.
2. **Scrubbed subprocess env** — `engine_env()` strips every key/cookie var in `BLOCKED_ENV`
   (X/Brave/Exa/Serper/OpenAI/Gemini/etc.) before the engine runs, so even if this machine later
   has those keys, the engine cannot reach a non-keyless source.
3. **`EXCLUDE_SOURCES`** — a belt-and-suspenders ban-list (x, tiktok, instagram, threads, bluesky,
   truthsocial, perplexity, pinterest, xiaohongshu, digg, …) passed to the engine.

The vendored engine additionally has the cookie/credential modules **deleted** (see
[`engine/VENDORED.md`](../engine/VENDORED.md)). No API keys or `.env` live in this repo; `gh` and
`claude` carry their own auth.

## 5. Tech stack & prerequisites

- **Python 3.12+** (engine hard requirement). Orchestrator and engine are **pure stdlib — zero pip
  packages**. The included `requirements.txt` files are intentionally empty/comment-only.
- **External CLIs:** `gh` (authed — gates the GitHub source), `yt-dlp` (gates YouTube), `claude`
  (headless query-planning, synthesis, and the judges).
- **Platform:** Windows-first launchers (`run.cmd`, `scripts/run-daily.ps1`); the Python is portable.

## 6. Portability findings (resolved 2026-06-22)

This repo was built under a different Windows profile (`terri`). Hardcoded per-user Python paths were
the migration blocker. All now resolve user-agnostically:

| File | Was | Now |
|---|---|---|
| `run.cmd` | `C:\Users\terri\…\Python313\python.exe` (→ `py -3.13`) | `%LOCALAPPDATA%\…\Python313\python.exe` → `py -3.13` → `py -3.12` → `python` |
| `src/orchestrator.py` (`PY313`) | same `terri` path | derived from the current user's `LOCALAPPDATA` |
| `scripts/run-daily.ps1` | `terri` 3.13/3.12 paths | derived from `$env:LOCALAPPDATA` + PATH discovery |
| `README.md` | `terri` path in prereqs | user-agnostic + a "Running in a fresh environment" section |

Note: `resolve_python()` (`orchestrator.py:126`) already short-circuits to `sys.executable` whenever
the orchestrator is launched by any 3.12+ interpreter — so the derived per-user path is only ever a
secondary fallback. `GH_DIR` (`C:\Program Files\GitHub CLI`) is a standard machine-wide path with a
PATH fallback and is left as-is.

## 7. Extensibility — adding what you track

**Daily topics** — add a stream/topics block to [`config/topics.yaml`](../config/topics.yaml); no code
change. A stream named `anthropic` is pinned to the top of the dashboard (see
`metrics.extract_section`).

**Tool / skill-as-a-service due-diligence** — add a block to
[`config/tools.yaml`](../config/tools.yaml) and run `.\run dd "<name>"`. Each brief now **leads with an
Availability scorecard** answering the skill-as-a-service question at a glance — *Official skill? MCP
server? SDK/CLI? Install path? Maturity tier (GA/Beta/Experimental/Community-only/None)?* — followed by
Integration map · Gotchas + environments · Historical record · References + sentiment. The portable
[`skills/tool-dd`](../skills/tool-dd/SKILL.md) wrapper adds a WebSearch-grounded layer for a richer,
doc-grounded scorecard; the baked-in `dd` command is keyless + autonomous and honest about thin
evidence (an unsupported field reads **Unknown**, never a guess).

## 8. Maturity & risk notes

- **Deterministic `dd` plan** — the due-diligence query plan is code, not LLM-generated, so a
  scheduled run never depends on a planner LLM being reachable (`duediligence.dd_plan`).
- **Faithfulness gate** — the judge weights faithfulness highest and fires a red dashboard banner
  below 70, surfacing fabricated/unsupported citations as the primary QE trust signal.
- **Thin-evidence honesty** — synthesis is instructed to state "not found / Unknown" rather than
  invent, in both the digest and the `dd` scorecard.
- **Single tracked artifact** — only `metrics/kpi.jsonl` is committed; digests/briefs are reproducible
  from `raw/` via `rerender`.
- **Open items** — Windows-only launchers (no `*.sh` wrapper); `claude`/`gh`/`yt-dlp` must be on PATH
  or the corresponding capability silently degrades (surfaced by `.\run doctor`).
