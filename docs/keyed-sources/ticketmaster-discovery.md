# Ticketmaster Discovery API

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` &nbsp;·&nbsp; **Path:** `K` (free-key opt-in) &nbsp;·&nbsp; **Tier:** free-key
> &nbsp;·&nbsp; **Last verified:** 2026-07-20

**Env var(s):** `TM_API_KEY` *(proposed name — not yet wired)*
**Config lane(s) served:** `todo`, potentially `topics` (a local-events pulse)

The best keyed source for **ticketed events** — concerts, sports, theater. Complements the
place-and-activity focus of NPS/RIDB with time-bound "what's on."

## What it unlocks
The Discovery API searches 230k+ live events with dates, venues, and categories — the piece Reddit/YouTube
social proof covers only unevenly. For a `todo` place it can add a "happening soon nearby" section; as a
`topics` sub-lane it could power a recurring local-events digest.

## Cost & limits
**Free key**, self-serve. ~5,000 calls/day, ~5 requests/sec. Attribution required; standard developer
terms. No card for the free tier.

## ToS & storage compatibility
Attribution required. Standard developer terms permit the reads this tool does; no blanket
no-storage clause of the Google/Yelp kind. Re-check attribution wording before shipping.

## How we'd leverage it
Not wired. Keyed opt-in per the [reusable wiring recipe](README.md#reusable-wiring-recipe): a
`src/events_keyed.py` reading `TM_API_KEY`, no-op when unset, merged into the target lane's `web_md`
after synthesis. Never added to the engine env. This is the concrete "Phase 3 free-key side-lane" the
travel report sketched.

## Verification snippet
```powershell
# 200 + JSON _embedded.events confirms a working key; 401 confirms the key requirement.
curl.exe -s "https://app.ticketmaster.com/discovery/v2/events.json?size=1&apikey=<your-key>"
```

## Sources
- [Ticketmaster — Getting Started](https://developer.ticketmaster.com/products-and-docs/apis/getting-started/) — free key, 5k/day, ~5 rps
- [Discovery API v2](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/) — 230k+ events
- Deep-dive context: [travel data-avenues report §03/§06](../../reports/things-to-do-data-avenues-2026-07-20.html)
