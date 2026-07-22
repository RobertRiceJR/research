# Keyless-open sources (no key — the free wins)

*↩ [Keyed-Source Register](README.md)*

> **Status:** trio `wired` · others `idea` &nbsp;·&nbsp; **Path:** `A+` (keyless open API) &nbsp;·&nbsp;
> **Tier:** open (no key) &nbsp;·&nbsp; **Last verified:** 2026-07-20

**Env var(s):** none — that's the point.
**Config lane(s) served:** `todo` today; `A+` sources fit any lane needing structured facts

Not every "authoritative structured source" needs a key. This page tracks **open APIs** that give the same
kind of data a keyed source would, with **no credential**, so before spending a `K` on something, check
whether an `A+` source already covers it. Listed here as the honest counterweight to the keyed tiers.

## Already wired (reference — how an A+ source looks in this repo)
[`src/places_open.py`](../../src/places_open.py) enriches the `todo` lane with three keyless, GET-only
sources, merged via the `web_md` hook (best-effort; a miss degrades to social-only):

| Source | What it gives | License | Reliability |
| --- | --- | --- | --- |
| **Wikivoyage** (MediaWiki API) | Curated destination-guide intro + canonical link | CC BY-SA 4.0 | reliable |
| **Wikipedia GeoSearch** (GeoData) | Notable POIs near a coordinate | CC BY-SA | reliable |
| **OpenStreetMap Overpass** | `tourism`/`historic` POIs near a coordinate | ODbL | best-effort (public instance 429/504s) |

These prove the `A+` pattern: a small stdlib fetcher in `src/`, no key, no cookies, no `Authorization`
header, isolated from the engine env — the keyless analog of the [NPS](nps.md) keyed pattern.
**Share-alike caveat:** Wikivoyage (CC BY-SA) and OSM (ODbL) require attribution + share-alike if you ever
redistribute derived text/data. Synthesis already cites every source URL verbatim.

## Not the same as "no key" — a correction
[Recreation.gov / RIDB](recreation-gov-ridb.md) *looks* like it belongs here but its `/facilities`
endpoint returns **HTTP 401 without a free key** (verified 2026-07-20). It lives in the keyed **K** tier,
not here. Noted so the mistake isn't repeated.

## Candidate A+ sources not yet wired (`idea`)
Plausible keyless open APIs to reach for before any keyed source — unverified until someone checks terms +
a live call:
- **Other MediaWiki endpoints** — e.g. Wikipedia extracts/pageviews for a `dd`/`scorecard` subject's notability.
- **Government open-data feeds** (data.gov and agency APIs) — many are keyless GET; check per endpoint.
- **RSS / Atom feeds** — tourism-board "this weekend" pages, release notes, changelogs (Path A+/B; no key).

When you wire one, follow the [reusable wiring recipe](README.md#reusable-wiring-recipe) (the keyless
variant: no env var at all) and flip it to `wired` here.

## Sources
- [`src/places_open.py`](../../src/places_open.py) — the wired keyless trio + `open_data_notes` merge
- [`README.md` — Things-to-do open data](../../README.md) — the security note on this keyless-open path
- Deep-dive taxonomy: [travel data-avenues report §02/§04](../../reports/things-to-do-data-avenues-2026-07-20.html)
