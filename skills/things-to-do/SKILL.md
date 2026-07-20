---
name: things-to-do
version: "0.1.0"
description: >-
  Things-to-do research for a place or activity. Given a destination, find the top
  experiences worth doing, the hidden gems locals pick, what to know before you go,
  and what's overrated — blending keyless community evidence (Reddit, YouTube) with
  WebSearch-grounded facts from travel sites (TripAdvisor, Atlas Obscura, tourism
  boards). Produces a 4-section shareable HTML brief. Use when the user asks "things
  to do in <place>", "is <attraction> worth it", "plan a visit to <place>", or
  "research <place> for a trip".
allowed-tools: WebSearch, WebFetch, Bash, Read, Write
---

# Things-To-Do Research (`things-to-do`)

Plug in a place → get a 4-section brief:
**Top things to do · Hidden gems & local picks · Know before you go · Overrated / skip.**

This skill has TWO grounding layers. Run BOTH for a full brief; the keyless engine alone
misses editorial/official facts (attractions, hours, ticketing, festivals), and WebSearch
alone misses what visitors actually report. The keyless `todo` command already folds in
open-data facts (Wikivoyage / Wikipedia GeoSearch / OpenStreetMap); this skill adds the
review-site layer the keyless contract can't reach directly.

## Step 0 — Load WebSearch

First tool call, every time:

```
ToolSearch select:WebSearch,WebFetch
```

## Step 1 — WebSearch the editorial / official facts (the richest layer)

Run 3-4 searches. Adapt the queries to the place, but cover these angles:

1. `"<place> best things to do <year>"` — the headline attractions
2. `"<place> hidden gems local tips reddit"` — what locals/regulars recommend
3. `"<place> events festivals this month"` — what's on right now (timely)
4. `"<place> overrated tourist trap OR worth it"` — sentiment / what to skip

Capture, for each finding: the claim + a VERBATIM source URL (TripAdvisor listing, Atlas
Obscura page, official tourism board, NPS/park page, a news "things to do" roundup). Read a
page with WebFetch when you need specifics (hours, ticket price, seasonality). You will hand
these to synthesis as authoritative "web notes." Respect attribution; do not bulk-copy — cite
and summarize.

## Step 2 — Run the keyless engine for community evidence

```bash
.\run todo "<place>" --engine-only
```

This runs the vendored last30days engine (keyless: Reddit, HN, GitHub, YouTube) with a
things-to-do query plan and prints the raw ranked evidence. It does NOT synthesize — that's
your job, so you can merge in the Step 1 web notes. If the place is already in
`config/todo.yaml`, its `subreddits` hint sharpens retrieval; if not, add a block there first
(plug-and-play) or just run the command ad-hoc.

## Step 3 — Synthesize the 4-section brief

Merge Step 1 (web notes, authoritative) + Step 2 (engine evidence, visitor signal) into
EXACTLY this markdown shape, then write it to the brief:

```
_Worth it:_ **<Act|Watch|Ignore>** - <3-8 word reason>

## Top things to do
- **<lead-in>** - the experience + why it's worth it [<source>](<url>)

## Hidden gems & local picks
- **<lead-in>** - the local/off-the-beaten-path pick [<source>](<url>)

## Know before you go
- **<lead-in>** - timing / cost / tickets / parking / crowds / seasonality [<source>](<url>)

## Overrated / skip
- **<lead-in>** - what's not worth it (or say so plainly if nothing) [<source>](<url>)
```

Rules: every factual bullet ends with a verbatim inline `[name](url)` link — never invent a
URL. Lead with concrete, actionable picks. `Act` = go, `Watch` = maybe/depends, `Ignore` =
skip. If a section has no grounding, say so plainly rather than padding.

## Step 4 — Render the shareable HTML brief

Save your synthesis markdown and render it with the repo's brief renderer:

```bash
python -c "import sys; sys.path.insert(0,'src'); from render_digest import render_brief; from pathlib import Path; md=Path('raw/<date>/<slug>-todo-synthesis.md').read_text(encoding='utf-8'); Path('briefs').mkdir(exist_ok=True); Path('briefs/<slug>-<date>.html').write_text(render_brief('<place>', md, ['reddit','youtube'], {'date':'<date>'}), encoding='utf-8')"
```

Confirm the path to the user. The brief is self-contained dark-mode HTML, shareable as-is.

## Headless alternative

For an autonomous (no-WebSearch) brief — scheduled runs, or when you just want the community +
open-data picture — skip Steps 1/3/4 and run the baked-in command, which synthesizes via
headless Claude, folds in the keyless open-data quartet, and writes the brief itself:

```bash
.\run todo "<place>"        # one place (social proof + open-data enrichment)
.\run todo --all            # every place in config/todo.yaml
.\run todo "<place>" --no-open-data   # social evidence only
```

This is honest about its limits: editorial/review-site facts get a thin-evidence note. The
WebSearch path above is materially richer for current events and attraction specifics.
