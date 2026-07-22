# Web-search providers (Brave · Exa · Serper · Parallel)

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` (banned by design) &nbsp;·&nbsp; **Path:** `K` &nbsp;·&nbsp; **Tier:** free-key → paid
> &nbsp;·&nbsp; **Last verified:** 2026-06-18 *(from the vendored engine's env.py)*

**Env var(s):** `BRAVE_API_KEY` · `EXA_API_KEY` · `SERPER_API_KEY` · `PARALLEL_API_KEY`
**Config lane(s) served:** in principle every lane — general web breadth beyond social

Keyed web-search backends the engine can carry. All four env vars are stripped in
[`BLOCKED_ENV`](../../src/orchestrator.py#L52-L58). Notable because this repo already has a **keyless
substitute** for their entire job.

## What they unlock
General web results (news, docs, blogs, vendor pages) to broaden a query past the social sources — useful
for `dd`/`scorecard`/`todo` where authoritative pages matter.

## Cost & limits
Mixed: Brave and Serper have small free tiers then paid; Exa and Parallel are paid-leaning. All
per-query metered.

## The keyless substitute (why you don't need a key)
This is the cleanest **Path B** story in the repo. The *hosting Claude* has WebSearch/WebFetch and can pull
cited web facts with **no key at all** — that's exactly what [`skills/tool-dd`](../../skills/tool-dd/SKILL.md)
does: run a lane `--engine-only` for raw keyless evidence, then let Claude layer cited web facts, merged
through the lane's `web_md` hook. So a web-search *key* buys little that Path B doesn't already give you
for free, while adding cost and breaking the keyless contract.

## ToS & storage compatibility
Provider-specific; generally permit storing returned snippets, but confirm per provider. The Path B route
sidesteps this by having Claude read/cite public pages directly.

## What you'd do instead
Use the WebSearch skill pattern (Path B). Reserve a paid search key only if you hit a hard automation need
that Claude's own WebSearch can't satisfy — and then isolate it per the
[reusable wiring recipe](README.md#reusable-wiring-recipe), never in the engine env.

## Sources
- [`engine/lib/env.py`](../../engine/lib/env.py#L370-L404) — `BRAVE_API_KEY` / `EXA_API_KEY` / `SERPER_API_KEY` / `PARALLEL_API_KEY`
- [`src/orchestrator.py:52-58`](../../src/orchestrator.py#L52-L58) — stripped in `BLOCKED_ENV`
- [`skills/tool-dd/SKILL.md`](../../skills/tool-dd/SKILL.md) — the keyless Path B substitute
