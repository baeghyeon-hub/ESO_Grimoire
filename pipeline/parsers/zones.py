"""
존 파서 — {{Online Place Summary|type=Zone}} 에서 존 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pipeline.parsers.common import extract_template_params, clean_wikitext_inline

_LOG = logging.getLogger(__name__)


@dataclass
class ParsedZone:
    name: str
    page_title: str
    zone_type: str = ""       # zone, city, dlc_zone
    dlc: str = ""
    alliance: str = ""
    wayshrines: int = 0
    delves: int = 0
    public_dungeons: int = 0
    group_dungeons: int = 0
    world_bosses: int = 0
    skyshards: int = 0
    set_stations: int = 0
    quests: int = 0
    hub: str = ""
    description: str = ""


def parse_zone(title: str, wikitext: str) -> ParsedZone | None:
    """존 wikitext를 파싱하여 ParsedZone 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online Place Summary")
    if not params:
        return None

    place_type = params.get("type", "").strip().lower()
    if place_type not in ("zone", "city", "settlement", "region"):
        return None

    name = title.replace("Online:", "").strip()

    # DLC
    dlc = ""
    dlc_m = re.search(r"\{\{Mod Header\|([^}|]+)", wikitext)
    if dlc_m:
        dlc = dlc_m.group(1).strip()

    result = ParsedZone(
        name=name,
        page_title=title,
        zone_type=place_type,
        dlc=dlc,
        alliance=params.get("alliance", "").strip(),
        wayshrines=_safe_int(params.get("wayshrines", "0")),
        delves=_safe_int(params.get("delves", "0")),
        public_dungeons=_safe_int(params.get("publicdungeons", "0")),
        group_dungeons=_safe_int(params.get("groupdungeons", "0")),
        world_bosses=_safe_int(params.get("worldbosses", "0")),
        skyshards=_safe_int(params.get("skyshard", "0")),
        set_stations=_safe_int(params.get("setstations", "0")),
        quests=_safe_int(params.get("quests", "0")),
        hub=clean_wikitext_inline(params.get("hub", "")),
        description=clean_wikitext_inline(params.get("description", "")),
    )

    return result


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return 0
