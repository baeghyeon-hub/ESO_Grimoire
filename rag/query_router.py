"""
Query Router — Hybrid Routing to classify user queries.

Strict Mode (DB priority):
  Set names, stats, farming locations -> inject DB results into context
  LLM answers based on provided data only

Creative Mode (LLM autonomous):
  Recommendations, comparisons, meta, builds -> grant LLM tool access
  LLM decides when to search DB/wiki
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

_LOG = logging.getLogger(__name__)


class RouteMode(Enum):
    STRICT = "strict"      # DB priority
    CREATIVE = "creative"  # LLM autonomous (with tools)


@dataclass
class RouteResult:
    mode: RouteMode
    db_context: str = ""                   # Strict: pre-fetched DB context
    detected_sets: list[str] = field(default_factory=list)
    detected_stats: list[str] = field(default_factory=list)
    detected_locations: list[str] = field(default_factory=list)
    is_lore: bool = False                  # Lore/narrative query detected
    reason: str = ""                       # Debug info


# ── Keyword dictionaries ──────────────────────────────────

_CREATIVE_KEYWORDS = {
    "recommend", "compare", "vs", "meta", "build", "setup",
    "best", "optimal", "alternative", "better", "which",
    "combo", "pair", "synergy", "tier",
}

_STAT_KEYWORDS = {
    "crit": "Critical Chance",
    "critical": "Critical Chance",
    "penetration": "Offensive Penetration",
    "pen": "Offensive Penetration",
    "weapon damage": "Weapon Damage",
    "spell damage": "Spell Damage",
    "magicka": "Maximum Magicka",
    "stamina": "Maximum Stamina",
    "health": "Maximum Health",
    "recovery": "Recovery",
    "armor": "Armor",
    "healing": "Healing",
}

_LOCATION_KEYWORDS = {
    "farm": True, "drop": True, "where": True, "location": True,
    "obtain": True,
}

_LORE_KEYWORDS = {
    "lore", "history", "daedra", "daedric", "aedra", "aedric", "divines",
    "oblivion", "aetherius", "mundus", "nirn", "tamriel", "akavir",
    "mythology", "prophecy", "creation myth", "convention", "kalpa",
    "anu", "padomay", "sithis", "anui-el", "lorkhan", "akatosh",
    "molag bal", "mehrunes dagon", "sheogorath", "azura", "mephala",
    "boethiah", "nocturnal", "hermaeus mora", "hircine", "malacath",
    "vaermina", "clavicus vile", "meridia", "namira", "peryite",
    "sanguine", "trinimac", "magnus", "mara", "dibella", "stendarr",
    "zenithar", "kynareth", "arkay", "julianos", "talos",
    "dwemer", "ayleid", "chimer", "falmer", "maormer", "aldmer",
    "dunmer", "altmer", "bosmer", "orsimer", "khajiit", "argonian",
    "redguard", "breton", "nord", "imperial",
    "dragonborn", "nerevarine", "septim", "reman", "alessia",
    "tiber septim", "vivec", "sotha sil", "almalexia", "dagoth ur",
    "numidium", "red mountain", "white-gold", "planemeld", "soulburst",
    "interregnum", "first era", "second era", "third era", "fourth era",
    "merethic", "dawn era",
}


# ── Set name detection ───────────────────────────────────

_set_names_cache: set[str] | None = None


def _get_set_names() -> set[str]:
    """Load set names from DB (cached)."""
    global _set_names_cache
    if _set_names_cache is not None:
        return _set_names_cache

    try:
        from pipeline.db import _get_conn
        conn = _get_conn()
        rows = conn.execute("SELECT name FROM sets").fetchall()
        _set_names_cache = {r[0].lower() for r in rows}
        _LOG.info("[router] loaded %d set names", len(_set_names_cache))
    except Exception:
        _set_names_cache = set()

    return _set_names_cache


def _detect_set_names(query: str) -> list[str]:
    """Detect set names in query."""
    set_names = _get_set_names()
    query_lower = query.lower()
    found = []

    # Match longest names first (Mother's Sorrow > Sorrow)
    sorted_names = sorted(set_names, key=len, reverse=True)
    for name in sorted_names:
        if name in query_lower:
            found.append(name)
            # Remove matched part to prevent duplicate matches
            query_lower = query_lower.replace(name, " ")

    return found


def _detect_stats(query: str) -> list[str]:
    """Detect stat keywords in query."""
    q = query.lower()
    detected = []
    for keyword, stat in _STAT_KEYWORDS.items():
        if keyword in q and stat not in detected:
            detected.append(stat)
    return detected


def _detect_location_intent(query: str) -> bool:
    """Detect farming/drop location queries."""
    q = query.lower()
    return any(k in q for k in _LOCATION_KEYWORDS)


# ── DB context builder ─────────────────────────────────────

def _build_db_context(
    detected_sets: list[str],
    detected_stats: list[str],
    location_intent: bool,
) -> str:
    """Build DB context from detected keywords."""
    from pipeline.db import get_set_by_name, search_by_stat, init_db

    try:
        init_db()
    except Exception:
        return ""

    parts = []

    # Set info lookup
    for name in detected_sets[:3]:  # max 3 sets
        data = get_set_by_name(name)
        if not data:
            from pipeline.db import search_sets
            results = search_sets(name, limit=1)
            if results:
                data = get_set_by_name(results[0]["name"])

        if data:
            lines = [
                f"\n[Set: {data['name']}]",
                f"Type: {data['set_type'] or 'unknown'} | Armor: {data['armor_type'] or 'any'}",
                f"Location: {data['location'] or 'unknown'} | DLC: {data['dlc'] or 'base game'}",
                f"Craftable: {'Yes' if data['craftable'] else 'No'}",
                "Bonuses:",
            ]
            for b in data.get("bonuses", []):
                lines.append(f"  ({b['piece_count']}pc) {b['bonus_text']}")
            parts.append("\n".join(lines))

    # Stat-based set list
    for stat in detected_stats[:2]:  # max 2 stats
        results = search_by_stat(stat, limit=10)
        if results:
            seen = set()
            stat_lines = [f"\n[Sets with {stat}]"]
            for r in results:
                if r["name"] not in seen:
                    stat_lines.append(f"  - {r['name']} ({r['set_type']}, {r['piece_count']}pc)")
                    seen.add(r["name"])
            parts.append("\n".join(stat_lines))

    return "\n".join(parts) if parts else ""


# ── Main router ──────────────────────────────────────────

def route(query: str) -> RouteResult:
    """Analyze user query to determine Strict/Creative mode + build DB context."""
    q_lower = query.lower()

    # Creative keyword detection
    is_creative = any(k in q_lower for k in _CREATIVE_KEYWORDS)

    # Lore keyword detection
    is_lore = any(k in q_lower for k in _LORE_KEYWORDS)

    # Specific keyword detection
    detected_sets = _detect_set_names(query)
    detected_stats = _detect_stats(query)
    location_intent = _detect_location_intent(query)

    has_specific = bool(detected_sets or detected_stats or location_intent)

    # Mode decision
    if is_creative and not detected_sets:
        mode = RouteMode.CREATIVE
        reason = "creative keywords without specific set names"
    elif has_specific:
        mode = RouteMode.STRICT
        reason = f"specific: sets={detected_sets}, stats={detected_stats}, loc={location_intent}"
    elif is_creative:
        mode = RouteMode.CREATIVE
        reason = "creative keywords"
    else:
        mode = RouteMode.CREATIVE
        reason = "no specific pattern detected, LLM autonomous"

    # Build DB context for Strict mode
    db_context = ""
    if mode == RouteMode.STRICT:
        db_context = _build_db_context(detected_sets, detected_stats, location_intent)
        if not db_context:
            mode = RouteMode.CREATIVE
            reason += " -> fallback to creative (no DB results)"

    result = RouteResult(
        mode=mode,
        db_context=db_context,
        detected_sets=detected_sets,
        detected_stats=detected_stats,
        is_lore=is_lore,
        reason=reason,
    )

    _LOG.info("[router] mode=%s reason=%s sets=%s stats=%s lore=%s",
              mode.value, reason, detected_sets, detected_stats, is_lore)
    return result
