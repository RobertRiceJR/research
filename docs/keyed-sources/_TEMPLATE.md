<!--
COPY THIS FILE to <source>.md to add a source to the register, then:
  1. Fill in every field below (delete these HTML comments).
  2. Add one row to the lane table in README.md pointing at your new file.
Keep it factual and dated. NEVER paste a real key/token/cookie value into any field —
env vars appear here only by NAME.
-->

# <Source name>

> **Status:** `idea` | `researched` | `wired` | `avoid` &nbsp;·&nbsp; **Path:** `A` | `A+` | `B` | `K` | `✗`
> &nbsp;·&nbsp; **Tier:** open (no key) | free-key | paid &nbsp;·&nbsp; **Last verified:** YYYY-MM-DD

**Env var(s):** `<FOO_API_KEY>` *(name only — never a value)*
**Config lane(s) served:** `todo` / `topics` / `tools` / `agents` / `scorecards` / `recipes`

## What it unlocks
One or two sentences: the concrete capability a key would buy for *this lane*.

## Cost & limits
Free / paid tier, price shape, rate limits, quota. Note if a card is required even for a "free" tier.

## ToS & storage compatibility
Attribution requirements; whether the terms permit the raw-to-disk saves this tool does
([`orchestrator.py:322`](../../src/orchestrator.py#L322)). **Storage-forbidden ⇒ `avoid`.**

## How we'd leverage it
The specific wiring: which module, which lane hook, what the notes would look like. If `wired`, link the
code. If not, reference the [reusable wiring recipe](README.md#reusable-wiring-recipe).

## Verification snippet
A one-liner to confirm the key works (or that the source 401s without one). Names, not secrets.

## Sources
- <link> — what it establishes (dated)
