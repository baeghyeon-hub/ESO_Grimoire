"""
스킬 파서 — {{Online Skill Summary}} 템플릿에서 구조화된 스킬 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pipeline.parsers.common import extract_template_params, clean_wikitext_inline

_LOG = logging.getLogger(__name__)


@dataclass
class ParsedSkill:
    name: str
    page_title: str
    skill_line: str = ""
    cost: str = ""
    attrib: str = ""
    cast_time: str = ""
    target: str = ""
    duration: str = ""
    range: str = ""
    description: str = ""
    morph1_name: str = ""
    morph1_desc: str = ""
    morph2_name: str = ""
    morph2_desc: str = ""


def parse_skill(title: str, wikitext: str) -> ParsedSkill | None:
    """스킬 wikitext를 파싱하여 ParsedSkill 반환. 스킬이 아니면 None."""
    # 리다이렉트 스킵
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online Skill Summary")
    if not params:
        return None

    # 최소 조건: desc 또는 line 있어야 함
    if not params.get("desc") and not params.get("line"):
        return None

    name = title.replace("Online:", "").strip()

    result = ParsedSkill(
        name=name,
        page_title=title,
        skill_line=params.get("line", "").strip(),
        cost=_clean_cost(params.get("cost", "")),
        attrib=params.get("attrib", "").strip(),
        cast_time=params.get("casttime", "").strip(),
        target=params.get("target", "").strip(),
        duration=params.get("duration", "").strip(),
        range=params.get("range", "").strip(),
        description=_clean_desc(params.get("desc", "")),
        morph1_name=params.get("morph1name", "").strip(),
        morph1_desc=_clean_desc(params.get("morph1desc", "")),
        morph2_name=params.get("morph2name", "").strip(),
        morph2_desc=_clean_desc(params.get("morph2desc", "")),
    )

    return result


def _clean_cost(cost: str) -> str:
    """비용 텍스트 정제: {{ESO Magicka Link|2700}} → 2700 Magicka"""
    cost = clean_wikitext_inline(cost)
    return cost.strip()


def _clean_desc(desc: str) -> str:
    """설명 텍스트 정제."""
    if not desc:
        return ""
    # {{Nowrap|[N / N / N / N]}} → [N / N / N / N]
    desc = re.sub(r"\{\{Nowrap\|([^}]*)\}\}", r"\1", desc)
    desc = clean_wikitext_inline(desc)
    # 여러 공백 정리
    desc = re.sub(r"\s+", " ", desc)
    return desc.strip()
