"""
세트 파서 — wikitext에서 ESO 세트 데이터를 구조화 추출.

기존 pipeline/parser.py에서 이동.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

_LOG = logging.getLogger(__name__)


@dataclass
class SetBonus:
    piece_count: int
    bonus_text: str


@dataclass
class ParsedSet:
    name: str
    set_type: str = ""
    armor_type: str = ""
    location: str = ""
    dlc: str = ""
    craftable: bool = False
    description: str = ""
    bonuses: list[SetBonus] = field(default_factory=list)


_SET_TYPE_PATTERNS = [
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(overland set)", "overland"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(dungeon set)", "dungeon"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(trial set)", "trial"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(arena set)", "arena"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(mythic)", "mythic"),
    (r"Mythic Items?\|", "mythic"),
    (r"\{\{ESO Quality Color\|m\|Mythic\}\}", "mythic"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(monster set)", "monster"),
    (r"(?:is|as) (?:a|an) \[\[.*?\|?(PvP set)", "pvp"),
    (r"can be \[\[.*?\|?crafted\]\]", "craftable"),
    (r"craftable set", "craftable"),
]

_ARMOR_PATTERNS = [
    (r"\[\[(?:ON:|Online:)?Light Armor", "light"),
    (r"\[\[(?:ON:|Online:)?Medium Armor", "medium"),
    (r"\[\[(?:ON:|Online:)?Heavy Armor", "heavy"),
]


def _clean_location(loc: str) -> str:
    loc = re.sub(r"\[\[(?:ON:|Online:)?", "", loc)
    loc = loc.replace("]]", "")
    if "#" in loc:
        loc = loc.split("#", 1)[1]
    return loc.strip()


def parse_set(title: str, wikitext: str) -> ParsedSet | None:
    """세트 wikitext를 파싱하여 ParsedSet 반환. 세트가 아니면 None."""
    name = title.replace("Online:", "").strip()
    name = re.sub(r"\s*\(set\)\s*$", "", name, flags=re.IGNORECASE).strip()

    bonuses = _extract_bonuses(wikitext)
    if not bonuses:
        return None

    result = ParsedSet(name=name, bonuses=bonuses)
    intro = _get_intro(wikitext)

    for pattern, stype in _SET_TYPE_PATTERNS:
        if re.search(pattern, intro, re.IGNORECASE):
            result.set_type = stype
            break

    armor_types = []
    for pattern, atype in _ARMOR_PATTERNS:
        if re.search(pattern, intro):
            armor_types.append(atype)
    result.armor_type = ", ".join(armor_types)

    if re.search(r"can be \[\[.*?\|?crafted", intro, re.IGNORECASE):
        result.craftable = True
    if re.search(r"cannot be \[\[.*?\|?crafted", intro, re.IGNORECASE):
        result.craftable = False

    location = ""
    loc_m = re.search(
        r"(?:drops?|found|obtained|sold)\s+in\s+(?:the\s+)?\[\[(?:ON:|Online:)?([^\]|]+)",
        intro, re.IGNORECASE,
    )
    if loc_m:
        location = loc_m.group(1).strip()
    if not location:
        src_m = re.search(r"source=([^|}]+)", wikitext)
        if src_m:
            location = src_m.group(1).strip()
    result.location = _clean_location(location)

    dlc = ""
    dlc_match = re.search(r"\{\{Mod Header\|([^}|]+)", wikitext)
    if dlc_match:
        dlc = dlc_match.group(1).strip()
    if not dlc:
        dlc_m2 = re.search(r"dlc=([^|}]+)", wikitext)
        if dlc_m2:
            dlc = dlc_m2.group(1).strip()
    result.dlc = dlc

    result.description = _clean_intro(intro)
    return result


def _get_intro(wikitext: str) -> str:
    parts = re.split(r"===\s*Bonuses?\s*===", wikitext, maxsplit=1)
    return parts[0] if parts else wikitext


def _extract_bonuses(wikitext: str) -> list[SetBonus]:
    bonuses = []
    oi_match = re.search(r"<onlyinclude>(.*?)</onlyinclude>", wikitext, re.DOTALL)
    text = oi_match.group(1) if oi_match else wikitext

    pattern = re.compile(
        r"'''(\d+)\s*items?'''[:\s]*(.+?)(?=<br\s*/?>|'''|\n|$)",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        piece_count = int(match.group(1))
        bonus_text = _clean_bonus_text(match.group(2))
        if bonus_text:
            bonuses.append(SetBonus(piece_count=piece_count, bonus_text=bonus_text))

    if not bonuses:
        for line in text.split("\n"):
            line = line.strip()
            m = re.match(r"'''?(\d+)\s*items?'''?[:\s]*(.*)", line, re.IGNORECASE)
            if m:
                piece_count = int(m.group(1))
                bonus_text = _clean_bonus_text(m.group(2))
                if bonus_text:
                    bonuses.append(SetBonus(piece_count=piece_count, bonus_text=bonus_text))
    return bonuses


def _expand_eso_link(m: re.Match) -> str:
    stat_type = m.group(1)
    params_str = m.group(2) or ""
    params = [p.strip() for p in params_str.split("|") if p.strip()]
    if "Damage" in m.group(0) and "Link" in m.group(0):
        stat_type = stat_type + " Damage"
    if not params:
        return stat_type
    value = params[0] if re.match(r"[\d\-\.%]", params[0]) else ""
    suffix = ""
    for p in params:
        if p in ("y", ""):
            continue
        if p in ("Maximum", "Recovery") or (not re.match(r"[\d\-\.%]", p)):
            suffix = p
    parts = []
    if value:
        parts.append(value)
    if "Maximum" in value:
        parts.append(stat_type)
    elif suffix:
        parts.append(stat_type)
        parts.append(suffix)
    else:
        parts.append(stat_type)
    return " ".join(parts)


def _clean_bonus_text(text: str) -> str:
    text = re.sub(r"\{\{ESO (\w+) (?:Link|Damage Link)((?:\|[^}]*)?)\}\}", _expand_eso_link, text)
    text = re.sub(r"\{\{ESO Spell Damage Link[^}]*\}\}", "Spell Damage", text)
    text = re.sub(r"\{\{ESO Weapon Damage Link[^}]*\}\}", "Weapon Damage", text)
    text = re.sub(r"\[\[(?:ON:|Online:)?[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[(?:ON:|Online:)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"<br\s*/?>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'{2,3}", "", text)
    return text.strip()


def _clean_intro(intro: str) -> str:
    text = re.sub(r"\{\{[^}]*\}\}", "", intro)
    text = re.sub(r"__[A-Z]+__", "", text)
    text = re.sub(r"'{2,3}(.+?)'{2,3}", r"\1", text)
    text = re.sub(r"\[\[(?:ON:|Online:)?[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[(?:ON:|Online:)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines[0] if lines else ""
