"""
파서 레지스트리 — 도메인별 파서 함수를 중앙 등록.

각 파서는 (title, wikitext) → ParsedXxx | None 시그니처.
"""
from pipeline.parsers.sets import parse_set
from pipeline.parsers.skills import parse_skill
from pipeline.parsers.dungeons import parse_dungeon
from pipeline.parsers.zones import parse_zone
from pipeline.parsers.companions import parse_companion
from pipeline.parsers.alchemy import parse_reagent
from pipeline.parsers.quests import parse_quest
from pipeline.parsers.npcs import parse_npc

PARSERS = {
    "sets": parse_set,
    "skills": parse_skill,
    "dungeons": parse_dungeon,
    "trials": parse_dungeon,
    "arenas": parse_dungeon,
    "zones": parse_zone,
    "companions": parse_companion,
    "alchemy": parse_reagent,
    "quests": parse_quest,
    "npcs": parse_npc,
}

__all__ = ["PARSERS", "parse_set", "parse_skill", "parse_dungeon",
           "parse_zone", "parse_companion", "parse_reagent",
           "parse_quest", "parse_npc"]
