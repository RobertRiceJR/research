---
name: scorecard
version: "0.1.0"
description: >-
  Turn a subjective "return me the best <X>" into a defensible answer: a WEIGHTED
  RUBRIC that makes "best" explicit, then a graded, ranked shortlist of the real
  candidates scored against it. Blends keyless community evidence (Reddit, HN,
  GitHub, YouTube) with WebSearch-grounded facts (docs, repos, benchmarks). Produces
  a 4-section shareable HTML brief. Use when the user asks "what's the best <X>",
  "grade/score these options", "which <tool/vendor/approach> should I pick", or
  "build me a scorecard/rubric for <X>".
allowed-tools: WebSearch, WebFetch, Bash, Read, Write
---

# Scorecard Research (`scorecard`)

Plug in a subject → get a 4-section brief:
**Scoring rubric · Graded shortlist · Close calls & tradeoffs · Adopt this.**

The point: "best" is subjective, so this makes the *definition* of best explicit (a
weighted rubric) BEFORE ranking, then shows where the ranking flips if you re-weight.
It's the general form of what this repo already does to itself in
[`src/judge.py`](../../src/judge.py) — a weighted LLM-as-judge panel (Relevance 0.30 /
Faithfulness 0.40 / Actionability 0.30). Reuse that as a worked example of a good rubric.

This skill has TWO grounding layers. Run BOTH for a full brief; the keyless engine alone
misses doc-only facts (official benchmarks, docs, feature matrices, changelogs), and
WebSearch alone misses what practitioners actually report.

## Step 0 — Load WebSearch

First tool call, every time:

```
ToolSearch select:WebSearch,WebFetch
```

## Step 1 — WebSearch the doc-grounded facts (the richest layer)

Run 3-5 searches. Adapt to the subject, but cover these angles:

1. `"<subject> comparison best <year>"` — who the real candidates are
2. `"<subject> benchmark OR evaluation criteria"` — how "best" is measured
3. `"<subject> scorecard OR rubric template github"` — existing rubrics to borrow from
4. `"<subject> review worth it site:reddit.com OR site:news.ycombinator.com"` — sentiment
5. (if applicable) an official docs/benchmark page — WebFetch it for the feature matrix

Capture, for each finding: the claim + a VERBATIM source URL. These become authoritative
"web notes." Respect attribution — cite and summarize, don't bulk-copy.

## Step 2 — Run the keyless engine for community + GitHub evidence

```bash
.\run scorecard "<subject>" --engine-only
```

Runs the vendored last30days engine (keyless: Reddit, HN, GitHub, YouTube) with a
scorecard query plan (templates / candidates / criteria / sentiment) and prints the raw
ranked evidence. It does NOT synthesize — that's your job, so you can merge in Step 1's web
notes. If the subject is already in `config/scorecards.yaml`, its `subreddits` /
`github_repos` / `criteria` / `weights` hints sharpen retrieval and seed the rubric; if
not, add a block there first (plug-and-play) or run ad-hoc.

## Step 3 — Synthesize the 4-section scorecard

Merge Step 1 (web notes, authoritative) + Step 2 (engine evidence, community signal) into
EXACTLY this markdown shape, then write it to the brief:

```
_Verdict:_ **<Adopt|Adapt|Hold>** - <best pick + 3-8 word reason>

## Scoring rubric
- **<Criterion>** (weight 0.NN) - what earns a high score [<source>](<url>)
(4-7 bullets; weights are decimals summing to ~1.0, a starting point the reader can re-weight;
 ground each criterion in evidence. Do NOT use a markdown table — the renderer only shows bullets.)

## Graded shortlist
- **<candidate>** (score /5) - one-line why it ranks here [<source>](<url>)
(3-6 candidates, ranked best-first)

## Close calls & tradeoffs
- **<lead-in>** - where the ranking flips if you re-weight, and which subjective call drives it [<source>](<url>)

## Adopt this
- **<lead-in>** - the single recommendation + the reusable rubric to keep [<source>](<url>)
```

Rules: every factual bullet ends with a verbatim inline `[name](url)` link — never invent a
URL. Make the subjectivity explicit (that's the whole value). `Adopt` = clear winner, `Adapt`
= winner but tailor it, `Hold` = no candidate clears the bar / evidence too thin. If a section
has no grounding, say so plainly rather than padding.

## Step 4 — Render the shareable HTML brief

Save your synthesis markdown and render it with the repo's brief renderer (pass scorecard
chrome via `meta`):

```bash
python -c "import sys; sys.path.insert(0,'src'); from render_digest import render_brief; from pathlib import Path; md=Path('raw/<date>/<slug>-scorecard-synthesis.md').read_text(encoding='utf-8'); Path('briefs').mkdir(exist_ok=True); Path('briefs/<slug>-<date>.html').write_text(render_brief('<subject>', md, ['reddit','hackernews','github','youtube'], {'date':'<date>','kind':'scorecard','emoji':'🧮','title':'Scorecard - <subject>','rerun':'python src/orchestrator.py scorecard \"<subject>\"'}), encoding='utf-8')"
```

Confirm the path to the user. The brief is self-contained dark-mode HTML, shareable as-is.

## Headless alternative

For an autonomous (no-WebSearch) scorecard — scheduled runs, or when you just want the
community + GitHub picture — skip Steps 1/3/4 and run the baked-in command, which
synthesizes via headless Claude and writes the brief itself:

```bash
.\run scorecard "<subject>"   # one subject
.\run scorecard --all         # every subject in config/scorecards.yaml
```

This is honest about its limits: doc-only facts (official benchmarks, feature matrices) get
a thin-evidence note. The WebSearch path above is materially richer for the rubric and the
candidate feature comparison.
