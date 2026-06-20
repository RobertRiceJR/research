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

## Layout

```
engine/        vendored keyless engine (last30days.py + lib/) · MIT · VENDORED.md
src/
  orchestrator.py   run / validate / doctor / kpi / rerender / judge
  render_digest.py  dark-mode digest (relevance sort, colored verdicts, per-bullet points)
  metrics.py        KPI store + dashboard (CFD, trends, breakdowns, watch list, quality)
  judge.py          3 cheap Haiku judges (Relevance / Faithfulness / Actionability)
  trending.py       Top-10 trending AI GitHub repos this week (keyless)
config/topics.yaml  research streams + topics
digests/  raw/  metrics/  (generated; gitignored except metrics/kpi.jsonl)
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

> **Use Python 3.13 explicitly** — bare `python` here is Anaconda 3.10, which the engine rejects.
> Either prefix with the full path, or use `pwsh -File scripts\run-daily.ps1 run` (it resolves Python + gh):
> ```powershell
> & "C:\Users\terri\AppData\Local\Programs\Python\Python313\python.exe" src\orchestrator.py run
> ```

```powershell
python src\orchestrator.py doctor                 # prereqs + active keyless sources
python src\orchestrator.py validate               # RAW engine output for QE judgment
python src\orchestrator.py run                     # research -> digest -> KPIs -> judge -> dashboard
python src\orchestrator.py run --no-judge          # skip the quality scorer
python src\orchestrator.py judge --date 2026-06-18 # re-score a day's digest only
python src\orchestrator.py kpi --backfill          # rebuild dashboard (seed from existing digests)
python src\orchestrator.py rerender                # re-emit digests after a style change
```

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
