"""Export harvested things-to-do into the "Let's Go!" activity-tracker contract.

Turns the `todo` lane's output (config/todo.yaml + the latest
raw/<date>/<slug>-todo-synthesis.md per place) into a normalized JSON array that
the "Let's Go!" app's importer (server/import.js) upserts into its `activities`
table. The JSON is the ONLY coupling between the two repos — no cross-repo imports.

Contract record (drive_time is intentionally omitted — the importer computes it
from the app's home location + lat/lon):

    {"source","source_key","title","category","season","notes","lat","lon","source_url"}

Reuses todo.load_todo (config reader), orch._slug (stable dedup key), and
places_open.resolve_coords (best-effort keyless geocode).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import orchestrator as orch  # sibling module; src/ is on sys.path at runtime
import todo as td


# --------------------------------------------------------------------------
# Category mapping: config/todo.yaml free-text category (+ title keywords) ->
# one of the 8 fixed "Let's Go!" categories (client/src/lib/constants.js).
# The app does CATEGORY_EMOJIS[category] lookups, so we MUST emit a valid enum.
# --------------------------------------------------------------------------
_APP_CATEGORIES = (
    "Arts & Crafts", "Day Trips", "Lakes & Swimming", "Hikes & Nature",
    "Rainy Day", "Food & Restaurants", "Seasonal", "Local Gems",
)

# Ordered (first hit wins). Keyword -> app category.
_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("lake", "beach", "swim", "splash", "pool", "water park"), "Lakes & Swimming"),
    (("food", "restaurant", "eat", "dining", "cafe", "pizza", "brewery"), "Food & Restaurants"),
    (("aquarium", "museum", "indoor", "rainy", "planetarium"), "Rainy Day"),
    (("art", "craft", "paint", "pottery", "maker"), "Arts & Crafts"),
    (("pumpkin", "festival", "holiday", "christmas", "seasonal", "harvest", "ski"), "Seasonal"),
    (("outdoor", "hike", "nature", "park", "trail", "garden", "forest", "dune", "canyon", "arboretum"),
     "Hikes & Nature"),
    (("landmark", "gem", "urban", "stroll", "history", "settlement", "downtown", "tour"), "Local Gems"),
)


# Compile each rule to a word-boundary-anchored regex so "eat" doesn't match
# inside "great" and plurals still hit ("dunes" via "dune", "outdoors" via "outdoor").
_CATEGORY_RES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")", re.IGNORECASE), cat)
    for kws, cat in _CATEGORY_RULES
)


def map_category(cfg_category: str | None, title: str) -> str:
    """Map a config category + title to a valid app category (default 'Day Trips')."""
    hay = f"{cfg_category or ''} {title}"
    for rx, app_cat in _CATEGORY_RES:
        if rx.search(hay):
            return app_cat
    return "Day Trips"


# --------------------------------------------------------------------------
# Synthesis -> concise notes (the card shows ~2 lines of notes)
# --------------------------------------------------------------------------
_VERDICT_RE = re.compile(r"^_[^_]+:_\s*\*\*([A-Za-z ]+)\*\*\s*[-–]\s*(.+)$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:https?://[^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _plain(s: str) -> str:
    s = _LINK_RE.sub(r"\1", s)          # [text](url) -> text
    s = _BOLD_RE.sub(r"\1", s)          # **text** -> text
    return s.strip()


def _first_top_pick(md: str) -> str:
    """Lead-in of the first bullet under '## Top things to do'."""
    lines = md.splitlines()
    in_section = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower().startswith("## top things to do")
            continue
        if in_section and stripped.startswith("- "):
            body = _plain(stripped[2:])
            # take the lead-in (before the first ' - ' / ' — ' separator)
            lead = re.split(r"\s[-–—]\s", body, maxsplit=1)[0]
            return lead.strip()
    return ""


def notes_from_synthesis(md: str) -> str:
    """Concise, plain-text notes: verdict + top pick + provenance."""
    verdict = reason = ""
    for ln in md.splitlines():
        m = _VERDICT_RE.match(ln.strip())
        if m:
            verdict, reason = m.group(1).strip(), _plain(m.group(2))
            break
    parts: list[str] = []
    if verdict:
        parts.append(f"Worth it: {verdict}" + (f" — {reason}" if reason else ""))
    pick = _first_top_pick(md)
    if pick:
        parts.append(f"Top pick: {pick}")
    parts.append("(via last30days brief)")
    return ". ".join(parts)


# --------------------------------------------------------------------------
# Locate the latest harvest artifacts for a place
# --------------------------------------------------------------------------
def _latest_synthesis(slug: str) -> Path | None:
    """Newest raw/<date>/<slug>-todo-synthesis.md, or None if never harvested."""
    matches = sorted(orch.RAW.glob(f"*/{slug}-todo-synthesis.md"))
    return matches[-1] if matches else None


def _latest_brief(slug: str) -> str | None:
    """Relative path to the newest briefs/<slug>-<date>.html, or None."""
    matches = sorted(orch.BRIEFS.glob(f"{slug}-*.html"))
    return f"briefs/{matches[-1].name}" if matches else None


# --------------------------------------------------------------------------
# Build one contract record from a config entry + its synthesis
# --------------------------------------------------------------------------
def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_activity(place_cfg: dict, synthesis_md: str, brief_path: str | None) -> dict:
    name = place_cfg["name"]
    lat = _to_float(place_cfg.get("lat"))
    lon = _to_float(place_cfg.get("lon"))
    if lat is None or lon is None:
        try:
            import places_open
            rlat, rlon = places_open.resolve_coords(name)
            lat = lat if lat is not None else rlat
            lon = lon if lon is not None else rlon
        except Exception:  # noqa: BLE001 — geocode is best-effort
            pass
    return {
        "source": "last30days",
        "source_key": orch._slug(name),
        "title": name,
        "category": map_category(place_cfg.get("category"), name),
        "season": "Any",
        "notes": notes_from_synthesis(synthesis_md),
        "lat": lat,
        "lon": lon,
        "source_url": brief_path,
    }


# --------------------------------------------------------------------------
# Export all researched places -> exports/lets-go/activities.json
# --------------------------------------------------------------------------
def export_all(out_path: Path | None = None) -> tuple[Path, list[dict], list[str]]:
    """Emit one record per config/todo.yaml place that has a synthesis on disk.

    Returns (out_path, records, skipped_names). Places with no synthesis yet are
    skipped (run `.\\run todo "<place>"` first).
    """
    out_path = out_path or (orch.ROOT / "exports" / "lets-go" / "activities.json")
    records: list[dict] = []
    skipped: list[str] = []
    for place in td.load_todo():
        name = place["name"]
        slug = orch._slug(name)
        synth = _latest_synthesis(slug)
        if not synth:
            skipped.append(name)
            continue
        md = synth.read_text(encoding="utf-8")
        records.append(to_activity(place, md, _latest_brief(slug)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return out_path, records, skipped
