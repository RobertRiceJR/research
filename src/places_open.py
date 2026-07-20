"""Open-data enrichment for the `todo` lane — keyless, GET-only structured sources.

Adds authoritative "what to do / what exists" notes on top of the keyless social
evidence, merged into synthesis via the existing `web_md` hook. Three sources, all
keyless (no API key, no cookies), all read-only:

  * Wikivoyage (MediaWiki API)     — curated destination guide intro   (CC BY-SA 4.0)  [reliable]
  * Wikipedia GeoSearch (GeoData)  — notable POIs near coordinates      (CC BY-SA)      [reliable]
  * OpenStreetMap (Overpass)       — tourism / historic POIs near a pt  (ODbL)          [best-effort*]

  * (Recreation.gov RIDB was evaluated but its /facilities endpoint returns HTTP 401
    without a free api key, so it is NOT keyless — it belongs with the keyed opt-ins
    like NPS, not here.)

  *The public Overpass instance is frequently overloaded (429/504); we make a single
  gentle request and simply skip its block when it isn't available.

SECURITY: this is new outbound network from src/ (distinct from the scrubbed engine
subprocess). It is deliberately keyless + GET/POST-of-a-query only: no Authorization
header, no cookies, no user credentials. Every call is best-effort with a short
timeout; any failure returns "" so the brief degrades to social-only rather than
breaking. It never touches engine_env / run_engine / the keyless allowlist.

Attribution: downstream synthesis cites every source URL verbatim. Wikivoyage/OSM are
share-alike (CC BY-SA 4.0 / ODbL); keep that in mind before redistributing derived text.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_UA = "last30days-dashboard/0.1 (keyless things-to-do lane; +https://github.com/mvanhorn/last30days-skill)"
_TIMEOUT = 12


# --------------------------------------------------------------------------
# Tiny best-effort HTTP helpers (stdlib only)
# --------------------------------------------------------------------------
def _get_json(url: str, params: dict | None = None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 (https only, no auth)
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 — enrichment is best-effort; never fatal
        return None


def _post_text(url: str, data: dict) -> str | None:
    try:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, headers={
            "User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            return resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Individual sources (each returns markdown bullets, or "" on miss)
# --------------------------------------------------------------------------
def wikivoyage_notes(place: str) -> str:
    """Wikivoyage destination-guide intro + canonical link (CC BY-SA 4.0)."""
    data = _get_json("https://en.wikivoyage.org/w/api.php", {
        "action": "query", "format": "json", "formatversion": 2,
        "prop": "extracts|info", "inprop": "url",
        "exintro": 1, "explaintext": 1, "redirects": 1, "titles": place,
    })
    if not data:
        return ""
    for p in data.get("query", {}).get("pages", []):
        if p.get("missing"):
            continue
        url = p.get("fullurl") or f"https://en.wikivoyage.org/wiki/{urllib.parse.quote(place)}"
        extract = " ".join((p.get("extract") or "").split()).strip()
        if not extract:
            return f"- **Wikivoyage guide** - a community travel guide exists for {place} [Wikivoyage]({url})"
        snippet = extract[:320].rsplit(" ", 1)[0] + ("…" if len(extract) > 320 else "")
        return f"- **Wikivoyage guide** - {snippet} [Wikivoyage]({url})"
    return ""


def wikipedia_geosearch_notes(lat: float | None, lon: float | None,
                              radius: int = 8000, limit: int = 8) -> str:
    """Wikipedia GeoData: notable articles near a coordinate (no key)."""
    if lat is None or lon is None:
        return ""
    data = _get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "formatversion": 2,
        "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": radius, "gslimit": limit,
    })
    if not data:
        return ""
    lines: list[str] = []
    for g in data.get("query", {}).get("geosearch", []):
        title = g.get("title")
        if not title:
            continue
        url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        lines.append(f"- **{title}** - notable place ~{int(g.get('dist', 0))} m away [Wikipedia]({url})")
    return "\n".join(lines)


def osm_overpass_notes(lat: float | None, lon: float | None,
                       radius: int = 3000, limit: int = 12) -> str:
    """OpenStreetMap Overpass: named tourism/historic POIs near a coordinate (ODbL)."""
    if lat is None or lon is None:
        return ""
    query = (
        f"[out:json][timeout:15];("
        f'node["tourism"](around:{radius},{lat},{lon});'
        f'node["historic"](around:{radius},{lat},{lon}););out center {limit * 3};'
    )
    raw = _post_text("https://overpass-api.de/api/interpreter", {"data": query})
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        kind = (tags.get("tourism") or tags.get("historic") or "point of interest").replace("_", " ")
        url = f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id')}"
        lines.append(f"- **{name}** - {kind} (OpenStreetMap) [OSM]({url})")
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def resolve_coords(place: str) -> tuple[float | None, float | None]:
    """Best-effort lat/lon from Wikipedia, then Wikivoyage, coordinates prop."""
    for host in ("en.wikipedia.org", "en.wikivoyage.org"):
        data = _get_json(f"https://{host}/w/api.php", {
            "action": "query", "format": "json", "formatversion": 2,
            "prop": "coordinates", "redirects": 1, "titles": place,
        })
        if not data:
            continue
        for p in data.get("query", {}).get("pages", []):
            coords = p.get("coordinates")
            if coords:
                return _f(coords[0].get("lat")), _f(coords[0].get("lon"))
    return None, None


# --------------------------------------------------------------------------
# Orchestrator: one merged notes block for the synthesis web_md hook
# --------------------------------------------------------------------------
def open_data_notes(place: str, location: str | None = None,
                    lat=None, lon=None) -> str:
    """Gather keyless open-data notes into one cited markdown block (or "").

    Coordinate-based sources (Wikipedia GeoSearch, OSM) need a lat/lon: use the
    config-provided one if present, else resolve from Wikipedia/Wikivoyage. Every
    source is independent and best-effort — a miss just drops that block.
    """
    lat, lon = _f(lat), _f(lon)
    if lat is None or lon is None:
        rlat, rlon = resolve_coords(place)
        lat = lat if lat is not None else rlat
        lon = lon if lon is not None else rlon

    blocks: list[str] = []
    wv = wikivoyage_notes(place)
    if wv:
        blocks.append("Wikivoyage (curated travel guide):\n" + wv)
    wg = wikipedia_geosearch_notes(lat, lon)
    if wg:
        blocks.append("Wikipedia GeoSearch (notable places nearby):\n" + wg)
    om = osm_overpass_notes(lat, lon)
    if om:
        blocks.append("OpenStreetMap (points of interest nearby):\n" + om)
    return "\n\n".join(blocks).strip()
