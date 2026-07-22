# Other social sources (Bluesky · Truth Social · Apify · Xiaohongshu)

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` (banned by design) &nbsp;·&nbsp; **Path:** `K` &nbsp;·&nbsp;
> **Tier:** mixed (free-cred → paid) &nbsp;·&nbsp; **Last verified:** 2026-06-18 *(from the vendored engine's env.py)*

**Config lane(s) served:** `topics` (niche/breaking chatter), occasionally `dd`/`agentdd`

A family of engine sources that share one go/no-go decision: each needs a credential, each module was
**deleted** from the keyless fork ([`engine/VENDORED.md`](../../engine/VENDORED.md)), and each env var is
stripped in [`BLOCKED_ENV`](../../src/orchestrator.py#L52-L58). Grouped because none warrants its own file
until there's a concrete reason to wire it.

| Source | Env var(s) | Tier | Notes |
| --- | --- | --- | --- |
| **Bluesky** | `BSKY_HANDLE` + `BSKY_APP_PASSWORD` | free credential | App password from bsky.app settings. The *cheapest* to enable (no paid key), if you ever wanted one keyed social source. Still breaks keyless. |
| **Truth Social** | `TRUTHSOCIAL_TOKEN` | cookie/bearer | Bearer token from browser dev tools — a cookie-style credential, same surface the fork removed. |
| **Apify (legacy TikTok)** | `APIFY_API_TOKEN` | paid | Legacy TikTok path; superseded by [ScrapeCreators](scrapecreators.md). |
| **Xiaohongshu** | `XIAOHONGSHU_API_BASE` | self-hosted service | Points at a local HTTP bridge (`is_xiaohongshu_available` health-probes it); CJK-market source, niche here. |

## What they unlock
Platform-specific discussion the five keyless sources don't cover — Bluesky's tech community, Truth
Social, TikTok (via Apify), and the Chinese-market Xiaohongshu. For this repo's AI-QE focus the marginal
signal is low.

## ToS & storage compatibility
Varies per platform; the token-based ones (Truth Social) re-introduce a session-credential surface. Diligence
per source before any storage-heavy use.

## What you'd do instead
**Path A / Path B** as everywhere else: the keyless engine catches cross-posted/discussed content, and a
WebSearch skill can cite public posts with no key. If one day a single keyed social source were worth it,
**Bluesky** is the least-bad choice (free app password, no scraping intermediary) — but it still needs the
deleted `bluesky` module restored and would end the keyless posture.

## Sources
- [`engine/lib/env.py`](../../engine/lib/env.py) — `is_bluesky_available` / `is_truthsocial_available` / `is_tiktok_available` / `is_xiaohongshu_available`
- [`engine/VENDORED.md`](../../engine/VENDORED.md) — `bluesky`, `truthsocial`, `tiktok`, `xiaohongshu_api` modules deleted
- [`src/orchestrator.py:52-58`](../../src/orchestrator.py#L52-L58) — env vars stripped in `BLOCKED_ENV`
