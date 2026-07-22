# Recreation.gov (RIDB)

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` &nbsp;·&nbsp; **Path:** `K` (free-key opt-in) &nbsp;·&nbsp; **Tier:** free-key
> &nbsp;·&nbsp; **Last verified:** 2026-07-20

**Env var(s):** `RIDB_API_KEY` *(proposed name — not yet wired)*
**Config lane(s) served:** `todo`

The federal-recreation sibling of [NPS](nps.md). **Correction of record:** an earlier docs summary called
this "no key" — it isn't. The RIDB `/facilities` endpoint returns **HTTP 401 without a free key**
(verified live 2026-07-20), so it belongs in the keyed **K** tier alongside NPS, *not* in the
[keyless-open](keyless-open.md) trio.

## What it unlocks
The RIDB (Recreation Information Database) covers federal facilities across all land-management agencies —
campsites, tours, permits, activities, points of interest. Broader than NPS (which is parks-only), so it's
the natural second keyed source for outdoors-heavy `todo` places.

## Cost & limits
Free key from [recreation.gov/use-our-data](https://www.recreation.gov/use-our-data). REST API,
~50 requests/min. No card.

## ToS & storage compatibility
Free & open U.S. Government data, reuse encouraged. No storage restriction — compatible with raw-to-disk
saves.

## How we'd leverage it
Not wired. Build it as a keyed opt-in mirroring [NPS](nps.md): either extend `src/parks_keyed.py` with a
second `RIDB_API_KEY`-gated function or add a sibling `src/rec_keyed.py`, merged into `cmd_todo`'s
`web_md` the same way. Follow the [reusable wiring recipe](README.md#reusable-wiring-recipe) — keep it out
of every engine-env structure.

## Verification snippet
```powershell
# 401 confirms the key requirement; 200 + JSON confirms a working key.
curl.exe -s -o NUL -w "%{http_code}" "https://ridb.recreation.gov/api/v1/facilities?limit=1"        # -> 401
curl.exe -s -H "apikey: <your-key>" "https://ridb.recreation.gov/api/v1/facilities?limit=1"          # -> 200
```

## Sources
- [Recreation.gov — Use Our Data](https://www.recreation.gov/use-our-data) — free key required, REST, 50/min
- [RIDB API docs](https://ridb.recreation.gov/docs) — free & open (US Gov)
- Deep-dive context: [travel data-avenues report §03/§06](../../reports/things-to-do-data-avenues-2026-07-20.html)
