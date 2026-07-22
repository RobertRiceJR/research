# National Park Service (NPS) API

*↩ [Keyed-Source Register](README.md)*

> **Status:** `wired` &nbsp;·&nbsp; **Path:** `K` (free-key opt-in) &nbsp;·&nbsp; **Tier:** free-key
> &nbsp;·&nbsp; **Last verified:** 2026-07-20

**Env var(s):** `NPS_API_KEY` *(40-char free key)*
**Config lane(s) served:** `todo`

The **one keyed source already wired** in this repo — the reference implementation every future keyed
entry should copy. It deliberately breaks the keyless contract, but only when the key is explicitly set,
and only for this one U.S. government source.

## What it unlocks
NPS publishes a literal **"Things To Do"** endpoint (`/api/v1/thingstodo`) — official, authoritative
activities near a national park, plus events, campgrounds, and alerts. For a place in
[`config/todo.yaml`](../../config/todo.yaml) that is (or is near) a national park, it adds a curated,
government-sourced section on top of the keyless social + open-data evidence.

## Cost & limits
Free. Register for a 40-character key at
[nps.gov/subjects/developer](https://www.nps.gov/subjects/developer/get-started.htm). Standard
government-API rate limits; no card required.

## ToS & storage compatibility
U.S. Government public data; attribution requested. No storage restriction — compatible with the tool's
raw-to-disk saves.

## How we'd leverage it (already wired)
Isolated exactly per the [rules of engagement](README.md#rules-of-engagement):

- [`src/parks_keyed.py`](../../src/parks_keyed.py) — reads *only* `NPS_API_KEY`, returns `""` when unset
  (so keyless `todo` output is byte-for-byte unchanged), best-effort `try/except`, emits markdown notes.
- Merged into the brief in [`cmd_todo` / `orchestrator.py:819-827`](../../src/orchestrator.py#L819-L827)
  via the lane's `web_md` hook, **after** synthesis.
- It is **never** added to `engine_env()`, `BLOCKED_ENV`, `KEYLESS_SOURCES`, `EXCLUDE_SOURCES`, or
  `run_engine` — the keyed call goes straight to the NPS API from `src/`, never through the engine.
- Documented in the [README security model](../../README.md).

## Verification snippet
```powershell
# With the key set, a matching place returns a JSON "data" array; unset -> the section is simply absent.
$env:NPS_API_KEY = "<your-key>"; .\run todo "Great Sand Dunes National Park"
```

## Sources
- [NPS Developer — Get Started](https://www.nps.gov/subjects/developer/get-started.htm) — free 40-char key
- [NPS API documentation](https://www.nps.gov/subjects/developer/api-documentation.htm) — Things-To-Do / events / campgrounds / alerts
