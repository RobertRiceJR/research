# X / Twitter

*↩ [Keyed-Source Register](README.md)*

> **Status:** `researched` (banned by design) &nbsp;·&nbsp; **Path:** `K` / `✗` &nbsp;·&nbsp;
> **Tier:** cookies / paid &nbsp;·&nbsp; **Last verified:** 2026-06-18 *(from the vendored engine's env.py)*

**Env var(s):** `AUTH_TOKEN` + `CT0` (browser cookies) · `XAI_API_KEY` (xAI backend) · `XQUIK_API_KEY` (Xquik backend)
**Config lane(s) served:** `topics`, `dd`, `agentdd` (X is where a lot of AI-stack chatter lives)

X/Twitter is the marquee "if only we had a key" source for the AI lanes — and the one the repo most
deliberately walls off, because its only auth paths are **session cookies** (the exact
cookie-harvesting this repo deleted) or **paid** API access.

## What it unlocks
Real-time X discussion: launch reactions, practitioner threads, "is X worth it" takes on tools/agents.
High-signal for `topics`, `dd`, and `agentdd`.

## Auth paths (all blocked)
From [`engine/lib/env.py`](../../engine/lib/env.py) (`get_x_source*`), in the engine's original priority:
- **Bird backend** — needs `AUTH_TOKEN` + `CT0`, i.e. **browser session cookies**. This is the cookie
  model the keyless fork exists to eliminate. `✗`.
- **xAI backend** — `XAI_API_KEY`, **paid**. `K`.
- **Xquik backend** — `XQUIK_API_KEY`, third-party paid. `K`.

All three env vars are stripped in [`BLOCKED_ENV`](../../src/orchestrator.py#L52-L58), and `x` is in
[`EXCLUDE_SOURCES`](../../src/orchestrator.py#L46-L49). The keyless fork also **deleted** every X backend
module (`bird_x`, `xurl_x`, `xai_x`, `xquik`) — see [`engine/VENDORED.md`](../../engine/VENDORED.md) — so
`get_x_source()` hard-returns `None`.

## ToS & storage compatibility
Cookie-based access violates X's automation terms and re-introduces the credential-theft surface this repo
removed. The paid backends carry their own redistribution limits. Either way, a hard posture change.

## What you'd do instead
**Path A** — the keyless engine already surfaces X links when people quote/discuss them on Reddit/HN/YouTube.
**Path B** — a WebSearch skill can read and cite a public X post without any key. Prefer both over ever
setting an X credential.

## Sources
- [`engine/lib/env.py`](../../engine/lib/env.py#L514-L563) — `get_x_source*` (keyless fork returns `None`)
- [`engine/VENDORED.md`](../../engine/VENDORED.md) — X backends deleted
- [`src/orchestrator.py:46-58`](../../src/orchestrator.py#L46-L58) — `EXCLUDE_SOURCES` + `BLOCKED_ENV`
