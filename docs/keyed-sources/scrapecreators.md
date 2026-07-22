# ScrapeCreators

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` (banned by design) &nbsp;·&nbsp; **Path:** `K` (paid) &nbsp;·&nbsp;
> **Tier:** paid &nbsp;·&nbsp; **Last verified:** 2026-06-18 *(from the vendored engine's env.py)*

**Env var(s):** `SCRAPECREATORS_API_KEY` *(also accepts the vendor's `SCRAPE_CREATORS_API_KEY` spelling)*
**Config lane(s) served:** every engine-backed lane — `topics`, `dd`, `agentdd`, `scorecard`, `recipe`, `todo`

The **single biggest unlock** in the engine's key catalog — and precisely why it's banned. It's the master
key for the whole paid-social family. Currently stripped in
[`BLOCKED_ENV`](../../src/orchestrator.py#L52-L58).

## What it unlocks
One key activates a large slice of [`engine/lib/env.py`](../../engine/lib/env.py):
- **Reddit enrichment** (`get_reddit_source` → `scrapecreators`) on top of the keyless public JSON.
- **Comment enrichment** for YouTube and TikTok (`youtube_comments` / `tiktok_comments`, opt-in via `INCLUDE_SOURCES`).
- Whole sources: **TikTok, Instagram, Threads, Pinterest** (`is_*_available` all gate on this one key).
- A **YouTube search fallback** when `yt-dlp` fails (`is_youtube_sc_available`).

## Cost & limits
Paid, per-call pricing (the engine even supports comma-separated **key rotation** to spread cost). No free
tier of note. Cost scales with every enriched item — meaningful for a daily loop across many topics.

## ToS & storage compatibility
Third-party scraping intermediary; you inherit its terms *and* the underlying platforms' terms. Treat
persistent storage of enriched content as legally gray — diligence required before any storage-heavy use.

## Why it's banned here (and what you'd do instead)
This repo's identity is keyless; adding the paid-social family would invert that. The engine modules it
would drive (`tiktok`, `instagram`, `threads`, `pinterest`, …) were **deleted** from the vendored fork
(see [`engine/VENDORED.md`](../../engine/VENDORED.md)), so even setting the key wouldn't reach them without
restoring code. **Preferred substitute:** the keyless engine already captures the *discussion* about these
platforms via Reddit/YouTube (**Path A**), and a WebSearch skill (**Path B**, like
[`skills/tool-dd`](../../skills/tool-dd/SKILL.md)) can cite public posts with no key.

## If you ever did wire it
This one genuinely lives *inside* the engine, so it's the exception to the "isolated `src/` module"
pattern — it would mean **un-pruning** engine modules and loosening `BLOCKED_ENV` / `EXCLUDE_SOURCES`.
That is a fork-level decision that abandons the keyless contract; do not do it piecemeal. Document it as a
new product posture, not a config tweak.

## Sources
- [`engine/lib/env.py`](../../engine/lib/env.py#L40-L47) — `SCRAPECREATORS_API_KEY` and every `is_*_available` gate
- [`engine/VENDORED.md`](../../engine/VENDORED.md) — the paid-social modules were deleted from this fork
- [`src/orchestrator.py:52-58`](../../src/orchestrator.py#L52-L58) — stripped in `BLOCKED_ENV`
