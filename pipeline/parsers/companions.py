"""
컴패니언 파서 — {{Online NPC Summary}} + 컴패니언 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from pipeline.parsers.common import (
    extract_template_params,
    clean_wikitext_inline,
    get_intro,
)

_LOG = logging.getLogger(__name__)


@dataclass
class CompanionSkill:
    skill_name: str
    skill_line: str = ""
    description: str = ""


@dataclass
class ParsedCompanion:
    name: str
    page_title: str
    race: str = ""
    gender: str = ""
    location: str = ""
    dlc: str = ""
    description: str = ""
    perk: str = ""
    skills: list[CompanionSkill] = field(default_factory=list)


def parse_companion(title: str, wikitext: str) -> ParsedCompanion | None:
    """컴패니언 wikitext를 파싱하여 ParsedCompanion 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online NPC Summary")
    if not params:
        return None

    # 컴패니언인지 확인 — "Companion" 키워드 포함 여부
    if "companion" not in wikitext.lower():
        return None

    name = title.replace("Online:", "").strip()

    # DLC
    dlc = ""
    dlc_m = re.search(r"\{\{Mod Header\|([^}|]+)", wikitext)
    if dlc_m:
        dlc = dlc_m.group(1).strip()

    # gender에서 HTML 코멘트 제거
    gender = params.get("gender", "").strip()
    gender = re.sub(r"<!--.*?-->", "", gender).strip()

    result = ParsedCompanion(
        name=name,
        page_title=title,
        race=params.get("race", "").strip(),
        gender=gender,
        location=clean_wikitext_inline(params.get("loc", "")),
        dlc=dlc,
    )

    # 설명 (인트로의 첫 문장)
    intro = get_intro(wikitext)
    desc_text = clean_wikitext_inline(intro)
    for line in desc_text.split("\n"):
        line = line.strip()
        if line and len(line) > 20 and name.split()[0] in line:
            result.description = line
            break

    # Companion Perk 추출: Companion Perk\n|...'''PerkName:''' description
    # 소유격 아포스트로피(')를 허용하기 위해 .+? 사용
    perk_m = re.search(
        r"Companion Perk[^']*'''(.+?)'''[:\s]*([^\n]+)",
        wikitext,
    )
    if perk_m:
        perk_name = perk_m.group(1).strip().rstrip(":")
        perk_desc = clean_wikitext_inline(perk_m.group(2))
        result.perk = f"{perk_name}: {perk_desc}"

    return result
