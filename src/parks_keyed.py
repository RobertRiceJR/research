"""NPS (National Park Service) enrichment — the ONLY keyed source in the todo lane.

Opt-in and isolated: reads its OWN `NPS_API_KEY` env var and calls the free NPS API's
"Things To Do" endpoint. A no-op when the key is unset, so the keyless default output
of the `todo` lane is byte-for-byte unchanged without a key.

SECURITY (do not weaken): `NPS_API_KEY` is read here and NOWHERE near the engine. It is
never added to `orchestrator.engine_env()`, `run_engine()`, `BLOCKED_ENV`, or the
`KEYLESS_SOURCES` allowlist. This deliberately breaks the keyless contract — but only
when a key is explicitly provided, and only for this one government source. Treat it as
a separate, documented, keyed capability (see the README security model), not a default.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

_UA = "last30days-dashboard/0.1 (things-to-do NPS opt-in)"
_TIMEOUT = 12


def _get_json(url: str, params: dict):
    try:
        req = urllib.request.Request(
            url + "?" + urllib.parse.urlencode(params),
            headers={"User-Agent": _UA, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — opt-in enrichment is best-effort; never fatal
        return None


def nps_notes(place: str, location: str | None = None, limit: int = 6) -> str:
    """Official NPS 'Things To Do' near a place, or "" when NPS_API_KEY is unset."""
    key = os.environ.get("NPS_API_KEY")
    if not key:
        return ""
    data = _get_json("https://developer.nps.gov/api/v1/thingstodo", {
        "q": place, "limit": limit, "api_key": key,
    })
    if not data:
        return ""
    lines: list[str] = []
    for it in (data.get("data") or [])[:limit]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        url = it.get("url") or "https://www.nps.gov/"
        lines.append(f"- **{title}** - official NPS thing-to-do [NPS]({url})")
    if not lines:
        return ""
    return "National Park Service (official, opt-in):\n" + "\n".join(lines)
