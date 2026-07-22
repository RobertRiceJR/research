# Keyed-Source Register

A living catalog of sources that would need an **API key, token, or cookie** — one this **keyless** repo
deliberately does *not* use today. For each one it records: what it unlocks, which config lane it would
serve, cost/limits/ToS, and *how we'd wire it if we ever chose to*. So when the configs research grows and
a keyed entry gets tempting, the due diligence is already done — look it up here instead of re-researching.

> **This is documentation only.** No keys live here. Nothing in this folder changes runtime behavior. The
> repo stays keyless by default (see [README security model](../../README.md)). Every entry describes a
> *hypothetical* opt-in and the exact isolated pattern for adding one — never an active credential.

**How to read an entry:** each source has a file here (e.g. [`nps.md`](nps.md)). Status is one of
`wired` (an opt-in that already exists in code) · `researched` (verified, ready to build) · `idea`
(plausible, not yet checked) · `avoid` (checked and rejected). Only **NPS** is `wired`.

---

## Rules of engagement

The spine of this repo's security model. A key is never a casual add — it's a deliberate, documented,
*isolated* opt-in. When you wire one, obey all five:

1. **Keyless is the default.** The engine only ever touches the five keyless sources (Reddit, Hacker News,
   Polymarket, GitHub, YouTube). A key is an exception you justify, not a convenience you reach for.
2. **Give it its own env var and read it in its own module.** Mirror [`src/parks_keyed.py`](../../src/parks_keyed.py):
   a small `src/<lane>_keyed.py` that reads *only* its own key, is a **no-op when the key is unset**
   (keyless output stays byte-for-byte unchanged), and is best-effort (`try/except`, never fatal).
3. **Keep it far away from the engine.** A keyed var must **never** be added to `engine_env()`,
   `BLOCKED_ENV`, `KEYLESS_SOURCES`, `EXCLUDE_SOURCES`, or `run_engine` in
   [`src/orchestrator.py`](../../src/orchestrator.py). The scrubbed subprocess env is what guarantees the
   engine can't reach a non-keyless source even on a machine that has the key — don't undermine it.
4. **Storage-incompatibility is a hard stop.** This tool persists raw evidence to disk
   ([`orchestrator.py` `run_engine`](../../src/orchestrator.py#L322)). Any source whose ToS forbids
   caching/storing content (Google Places, Yelp, Google Maps reviews) is **`avoid`** — not "needs a key,"
   but *structurally incompatible*. Their signal still reaches you free via discussion on Reddit/YouTube.
5. **Document it.** Name the new keyed capability in the [README security model](../../README.md) and flip
   its entry here to `wired`. A key that isn't written down is a surprise waiting to happen.

---

## Access-path taxonomy

Every source is rated by *how* you'd reach it — this is the column that actually decides "how would we
harvest it." Carried over verbatim from the travel due-diligence report so the whole register stays
consistent.

| Path | Meaning |
| --- | --- |
| **A** | **Keyless social lane** — Reddit/YouTube, already in the engine (social proof). No key. |
| **A+** | **Keyless open API** — no key; add as a small fetcher or WebFetch (structured facts). |
| **B** | **WebSearch/WebFetch enrichment** — the *hosting Claude* reads public pages and cites them; no key baked in. |
| **K** | **Free-key (or paid) opt-in** — breaks the keyless contract deliberately; isolate per the rules above. |
| **✗** | **Avoid** — ToS-forbidden, paid-gated, deprecated, or storage-incompatible. |

The best keyed data usually has a free **A / A+ / B** substitute that reaches the same signal without a
key. Prefer those before spending a **K**.

---

## Register — by config lane

Each config lane and its candidate sources. `(none yet — stub)` rows are deliberate: this register *is* a
growing to-do, and an empty lane is a prompt to research it when the need arises.

| Config lane | Command | Candidate sources | Best verdict so far |
| --- | --- | --- | --- |
| [`config/todo.yaml`](../../config/todo.yaml) | `todo` | [NPS](nps.md) `wired` · [Recreation.gov/RIDB](recreation-gov-ridb.md) `researched` · [Ticketmaster](ticketmaster-discovery.md) `researched` · [keyless-open trio](keyless-open.md) `wired` | Full deep-dive: [travel report](../../reports/things-to-do-data-avenues-2026-07-20.html) |
| [`config/topics.yaml`](../../config/topics.yaml) | `run` | [ScrapeCreators](scrapecreators.md) · [X/Twitter](x-twitter.md) · [other social](other-social.md) · [web-search providers](web-search-providers.md) | Keyless-by-contract; keys only deepen social/web reach |
| [`config/tools.yaml`](../../config/tools.yaml) | `dd` | [ScrapeCreators](scrapecreators.md) · [web-search providers](web-search-providers.md) *(via a WebSearch skill — Path B, no key)* | Path **B** already covered by [`skills/tool-dd`](../../skills/tool-dd/SKILL.md) |
| [`config/agents.yaml`](../../config/agents.yaml) | `agentdd` | [ScrapeCreators](scrapecreators.md) · [X/Twitter](x-twitter.md) | `(mostly stub — social keys only)` |
| [`config/scorecards.yaml`](../../config/scorecards.yaml) | `scorecard` | [web-search providers](web-search-providers.md) *(Path B)* | `(none keyed — stub)` |
| [`config/recipes.yaml`](../../config/recipes.yaml) | `recipe` | `(none yet — stub)` | Reddit/YouTube social proof is sufficient |
| *engine-wide (all lanes)* | — | [LLM reasoning providers](llm-reasoning-providers.md) | **Not needed** — the hosting Claude is the planner (LAW 7) |

---

## Reusable wiring recipe

The canonical move for adding a keyed source, proven by the one that exists. Five steps:

1. **Add the env var.** Pick a source-specific name (`<FOO>_API_KEY`). It's already gitignored — the
   [`.gitignore`](../../.gitignore) guards `.env` / `.env.*`. Never commit the value.
2. **Write an isolated module.** Copy [`src/parks_keyed.py`](../../src/parks_keyed.py#L1-L55) to
   `src/<lane>_keyed.py`. It reads *only* its own key via `os.environ.get(...)`, returns `""` when unset,
   wraps the network call in `try/except`, and emits markdown notes.
3. **Merge it in the lane's command.** Call it in the relevant `cmd_*` **after** synthesis and fold the
   result into the lane's `web_md` hook — exactly like `cmd_todo` merges NPS at
   [`orchestrator.py:819-827`](../../src/orchestrator.py#L819-L827).
4. **Keep it out of the engine.** Do **not** touch `engine_env()`, `BLOCKED_ENV`, `KEYLESS_SOURCES`,
   `EXCLUDE_SOURCES`, or `run_engine`. The keyed module talks to its API directly from `src/`, never
   through the engine subprocess.
5. **Document it.** Add the capability to the [README security model](../../README.md) and set this
   register entry to `wired`.

To **add a new source to this register**, copy [`_TEMPLATE.md`](_TEMPLATE.md) to `<source>.md`, fill it
in, and add one row to the lane table above.

---

*Verdicts are dated inside each file — API terms, pricing, and rate limits drift, so re-check the
`Last verified` line before acting on any entry.*
