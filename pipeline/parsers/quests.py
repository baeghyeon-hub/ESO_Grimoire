"""
퀘스트 파서 — {{Online Quest Header}} 템플릿에서 퀘스트 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pipeline.parsers.common import extract_template_params, clean_wikitext_inline

_LOG = logging.getLogger(__name__)


@dataclass
class ParsedQuest:
    name: str
    page_title: str
    quest_type: str = ""    # main, zone, dungeon, daily, guild, side
    zone: str = ""
    giver: str = ""
    location: str = ""
    dlc: str = ""
    skill_point: int = 0
    description: str = ""
    quest_id: int = 0
    prev_quest: str = ""
    next_quest: str = ""


def parse_quest(title: str, wikitext: str) -> ParsedQuest | None:
    """퀘스트 wikitext를 파싱하여 ParsedQuest 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online Quest Header")
    if not params:
        return None

    name = title.replace("Online:", "").strip()
    # "(quest)" 접미사 제거
    name = re.sub(r"\s*\(quest\)\s*$", "", name, flags=re.IGNORECASE).strip()

    # DLC
    dlc = ""
    dlc_m = re.search(r"\{\{Mod Header\|([^}|]+)", wikitext)
    if dlc_m:
        dlc = dlc_m.group(1).strip()

    # 스킬 포인트 보상 확인
    reward = params.get("reward", "")
    skill_point = 1 if "Skill Point" in reward else 0

    result = ParsedQuest(
        name=name,
        page_title=title,
        quest_type=params.get("type", "").strip().lower(),
        zone=clean_wikitext_inline(params.get("zone", "")),
        giver=clean_wikitext_inline(params.get("giver", "")),
        location=clean_wikitext_inline(params.get("loc", "")),
        dlc=dlc,
        skill_point=skill_point,
        description=clean_wikitext_inline(params.get("description", "")),
        quest_id=_safe_int(params.get("id", "0")),
        prev_quest=clean_wikitext_inline(params.get("prev", "")) or clean_wikitext_inline(params.get("prereq", "")),
        next_quest=clean_wikitext_inline(params.get("next", "")),
    )

    return result


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return 0
