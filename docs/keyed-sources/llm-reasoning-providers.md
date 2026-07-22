# LLM reasoning providers (OpenAI · xAI · Google/Gemini · OpenRouter)

*↩ [Keyed-Source Register](README.md)*

> **Status:** `avoid` — **not needed** (by design) &nbsp;·&nbsp; **Path:** `K` &nbsp;·&nbsp; **Tier:** paid
> &nbsp;·&nbsp; **Last verified:** 2026-06-18 *(from the vendored engine's providers.py)*

**Env var(s):** `OPENAI_API_KEY` · `XAI_API_KEY` · `GOOGLE_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_GENAI_API_KEY` · `OPENROUTER_API_KEY`
**Config lane(s) served:** none directly — these power the engine's *reasoning* (query planning + rerank), not a source

Included in the register so the answer to "should we add an LLM key?" is written down: **no**, and here's
the concrete reason. These are the odd entry — not a data source, but the engine's brain.

## What they'd unlock
Upstream, [`engine/lib/providers.py`](../../engine/lib/providers.py) uses one of these keys to run the
**query planner** and **result rerank** (`resolve_runtime` picks Gemini → OpenAI → xAI → OpenRouter by
which key is present). Without a key the engine falls back to a deterministic local planner/score.

## Why this repo needs none (LAW 7)
The orchestrator supplies its own planner: **the hosting Claude Code is the reasoning model.**
[`generate_plan` (orchestrator.py:270-289)](../../src/orchestrator.py#L270-L289) has Claude author the
JSON query plan, and [`synthesize`](../../src/orchestrator.py#L338-L344) + the Haiku
[`judge.py`](../../src/judge.py) panel do the reasoning — all via the `claude` CLI already on the machine.
So the engine's provider keys are redundant here: we get better planning from Claude at no extra key or
cost. All four vars are stripped in [`BLOCKED_ENV`](../../src/orchestrator.py#L52-L58).

## Cost & compatibility
Paid, per-token. Adding one would duplicate reasoning the repo already does for free through Claude, so
there is no upside — this stays `avoid` unless the architecture changes to drop the Claude planner.

## What you'd do instead
Nothing — the keyless Claude-as-planner path is the intended design. If you ever ran the engine *outside*
this orchestrator (bare, without the `claude` CLI), you'd set one of these; inside this repo you never
should.

## Sources
- [`engine/lib/providers.py`](../../engine/lib/providers.py) — `resolve_runtime` provider selection
- [`engine/lib/env.py`](../../engine/lib/env.py#L370-L404) — the provider key names
- [`src/orchestrator.py:270-289`](../../src/orchestrator.py#L270-L289) — Claude is the planner (LAW 7); keys stripped in `BLOCKED_ENV`
