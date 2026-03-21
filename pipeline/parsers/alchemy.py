"""
연금술 파서 — {{Ingredient Summary}} 템플릿에서 재료 데이터 추출.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pipeline.parsers.common import extract_template_params

_LOG = logging.getLogger(__name__)


@dataclass
class ParsedReagent:
    name: str
    page_title: str
    effect1: str = ""
    effect2: str = ""
    effect3: str = ""
    effect4: str = ""


def parse_reagent(title: str, wikitext: str) -> ParsedReagent | None:
    """연금술 재료 wikitext를 파싱하여 ParsedReagent 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Ingredient Summary")
    if not params:
        return None

    # 효과가 하나도 없으면 스킵
    if not any(params.get(f"eff{i}", "") for i in range(1, 5)):
        return None

    name = title.replace("Online:", "").strip()

    return ParsedReagent(
        name=name,
        page_title=title,
        effect1=params.get("eff1", "").strip(),
        effect2=params.get("eff2", "").strip(),
        effect3=params.get("eff3", "").strip(),
        effect4=params.get("eff4", "").strip(),
    )
