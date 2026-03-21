"""
NPC 파서 — {{Online NPC Summary}} 템플릿에서 NPC 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pipeline.parsers.common import extract_template_params, clean_wikitext_inline, get_intro

_LOG = logging.getLogger(__name__)


@dataclass
class ParsedNPC:
    name: str
    page_title: str
    race: str = ""
    gender: str = ""
    location: str = ""
    zone: str = ""
    reaction: str = ""
    services: str = ""
    description: str = ""


def parse_npc(title: str, wikitext: str) -> ParsedNPC | None:
    """NPC wikitext를 파싱하여 ParsedNPC 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online NPC Summary")
    if not params:
        return None

    name = title.replace("Online:", "").strip()

    # 존 추출 — location 에서 추론하거나 별도 패턴
    location = clean_wikitext_inline(params.get("loc", ""))
    zone = params.get("zone", "").strip()

    # services 추출 (store, quest giver 등)
    services_parts = []
    if params.get("store"):
        services_parts.append("Merchant")
    if params.get("follower"):
        services_parts.append("Quest Giver")

    # 설명 추출
    intro = get_intro(wikitext)
    desc = clean_wikitext_inline(intro)
    # 첫 의미 있는 줄
    description = ""
    for line in desc.split("\n"):
        line = line.strip()
        if line and len(line) > 15:
            description = line
            break

    return ParsedNPC(
        name=name,
        page_title=title,
        race=params.get("race", "").strip(),
        gender=params.get("gender", "").strip(),
        location=location,
        zone=zone,
        reaction=params.get("reaction", "").strip(),
        services=", ".join(services_parts),
        description=description,
    )
