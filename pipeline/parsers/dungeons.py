"""
던전 파서 — {{Online Place Summary}} 템플릿에서 던전/트라이얼/아레나 데이터 추출.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from pipeline.parsers.common import (
    extract_template_params,
    clean_wikitext_inline,
    get_section,
    get_intro,
)

_LOG = logging.getLogger(__name__)


@dataclass
class DungeonBoss:
    boss_name: str
    boss_type: str = ""  # boss, miniboss
    strategy: str = ""


@dataclass
class ParsedDungeon:
    name: str
    page_title: str
    dungeon_type: str = ""    # group_dungeon, trial, arena
    zone: str = ""
    dlc: str = ""
    group_size: int = 0
    min_level: int = 0
    description: str = ""
    bosses: list[DungeonBoss] = field(default_factory=list)
    set_names: list[str] = field(default_factory=list)


# 던전 타입 매핑
_CLASS_TYPE_MAP = {
    "group dungeon": "group_dungeon",
    "trial": "trial",
    "arena": "arena",
    "public dungeon": "public_dungeon",
}


def parse_dungeon(title: str, wikitext: str) -> ParsedDungeon | None:
    """던전 wikitext를 파싱하여 ParsedDungeon 반환."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return None

    params = extract_template_params(wikitext, "Online Place Summary")
    if not params:
        return None

    # class 필드로 던전 여부 판별
    place_class = params.get("class", "").strip().lower()
    if place_class not in _CLASS_TYPE_MAP:
        return None

    name = title.replace("Online:", "").strip()

    # DLC
    dlc = ""
    dlc_m = re.search(r"\{\{Mod Header\|([^}|]+)", wikitext)
    if dlc_m:
        dlc = dlc_m.group(1).strip()

    result = ParsedDungeon(
        name=name,
        page_title=title,
        dungeon_type=_CLASS_TYPE_MAP[place_class],
        zone=params.get("zone", "").strip(),
        dlc=dlc,
        group_size=_safe_int(params.get("group", "0")),
        min_level=_safe_int(params.get("minlevel", "0")),
        description=clean_wikitext_inline(params.get("description", "")),
    )

    # 보스 추출
    result.bosses = _extract_bosses(wikitext)

    # 드랍 세트 추출
    result.set_names = _extract_set_names(wikitext)

    return result


def _extract_bosses(wikitext: str) -> list[DungeonBoss]:
    """===Bosses=== 및 ===Minibosses=== 섹션에서 보스 이름 + 공략 추출."""
    bosses = []

    # 보스별 공략 텍스트 사전 추출 (Layout/Boss Mechanics 등)
    strategy_map = _extract_boss_strategies(wikitext)

    # Layout + Boss Mechanics 결합 텍스트 (fallback 검색용)
    combined_text = ""
    for heading in ("Boss Mechanics", "Layout", "Walkthrough", "Strategy"):
        section = get_section(wikitext, heading, level=2)
        if section:
            combined_text += "\n" + section

    for heading, btype in [("Bosses", "boss"), ("Minibosses", "miniboss")]:
        section = get_section(wikitext, heading, level=3)
        if not section:
            continue
        for line in section.split("\n"):
            line = line.strip()
            if not line.startswith("*"):
                continue
            # *[[ON:BossName|Display]], description
            m = re.search(r"\[\[(?:ON:|Online:)?([^\]|]+)", line)
            if m:
                boss_name = m.group(1).strip()
                strategy = strategy_map.get(boss_name, "")
                # Fallback: 보스 이름이 텍스트에 언급된 문단 추출
                if not strategy and combined_text and boss_name:
                    strategy = _extract_context_for_name(combined_text, boss_name)
                bosses.append(DungeonBoss(
                    boss_name=boss_name, boss_type=btype, strategy=strategy,
                ))

    return bosses


def _extract_context_for_name(text: str, name: str) -> str:
    """텍스트에서 특정 이름이 언급된 문단을 추출."""
    # 이름이 포함된 모든 위치에서 주변 문단 수집
    idx = text.find(name)
    if idx == -1:
        return ""

    # 문단 경계 찾기 (빈 줄 또는 === 헤딩)
    # 앞쪽 경계
    start = text.rfind("\n\n", 0, idx)
    h_start = text.rfind("===", 0, idx)
    start = max(start if start != -1 else 0, h_start if h_start != -1 else 0)

    # 뒤쪽 경계
    end = text.find("\n\n", idx)
    h_end = text.find("===", idx + len(name))
    if end == -1:
        end = len(text)
    if h_end != -1:
        end = min(end, h_end)

    paragraph = text[start:end].strip()
    # === 헤딩 마크업 및 잔여 = 기호 제거
    paragraph = re.sub(r"^={2,}[^=\n]*={2,}\s*$", "", paragraph, flags=re.MULTILINE)
    paragraph = re.sub(r"={3,}", "", paragraph)
    cleaned = clean_wikitext_inline(paragraph)
    # 헤딩 텍스트만 나온 경우 제외
    if len(cleaned) < 40:
        return ""
    return cleaned[:1000]


def _extract_boss_strategies(wikitext: str) -> dict[str, str]:
    """Layout/Boss Mechanics 등 섹션에서 보스 이름별 공략 텍스트 추출."""
    strategy_map: dict[str, str] = {}

    # 여러 섹션을 순서대로 탐색 (Boss Mechanics가 가장 정확)
    combined_text = ""
    for heading in ("Boss Mechanics", "Layout", "Walkthrough", "Strategy"):
        section = get_section(wikitext, heading, level=2)
        if section:
            combined_text += "\n" + section

    if not combined_text:
        return strategy_map

    # 패턴 1: ===Boss Name=== 또는 ===[[ON:Boss Name|Boss Name]]=== 하위 섹션
    # wiki 링크가 포함된 헤딩 처리
    boss_sections = re.split(r"===\s*([^=]+?)\s*===", combined_text)
    # boss_sections: [before, heading1, content1, heading2, content2, ...]
    if len(boss_sections) > 1:
        for i in range(1, len(boss_sections), 2):
            raw_name = boss_sections[i].strip()
            # [[ON:BossName|Display]] → Display, [[ON:BossName]] → BossName
            boss_name = clean_wikitext_inline(raw_name).strip()
            if not boss_name:
                continue
            if i + 1 < len(boss_sections):
                content = boss_sections[i + 1].strip()
                cleaned = clean_wikitext_inline(content)
                if len(cleaned) > 30:
                    strategy_map[boss_name] = cleaned[:1000]

    # 패턴 2: '''Boss Name''' 뒤의 텍스트 (하위 헤딩이 없는 경우)
    if not strategy_map:
        for m in re.finditer(r"'''([^']{3,50})'''[:\s]*([^\n]+(?:\n(?![=*#]).[^\n]*)*)", combined_text):
            boss_name = m.group(1).strip()
            content = m.group(2).strip()
            cleaned = clean_wikitext_inline(content)
            if len(cleaned) > 30:
                strategy_map[boss_name] = cleaned[:1000]

    # 패턴 3: Layout에서 보스 이름이 언급된 문단 추출 (위에서 못 잡은 경우)
    # 보스 이름이 문단에 포함되면 해당 문단 전체를 strategy로 사용
    if not strategy_map:
        paragraphs = re.split(r"\n\s*\n", combined_text)
        for para in paragraphs:
            cleaned = clean_wikitext_inline(para).strip()
            if len(cleaned) > 50:
                # 볼드 이름이 있으면 키로 사용
                bold_m = re.search(r"'''([^']{3,50})'''", para)
                if bold_m:
                    name = bold_m.group(1).strip()
                    strategy_map[name] = cleaned[:1000]

    return strategy_map


def _extract_set_names(wikitext: str) -> list[str]:
    """세트 이름 추출 — Sets 섹션 또는 {{Item Set}} 템플릿."""
    sets = []

    # Sets 섹션
    sets_section = get_section(wikitext, "Sets", level=2)
    if sets_section:
        # [[ON:SetName|...]] 패턴
        for m in re.finditer(r"\[\[(?:ON:|Online:)?([^\]|]+?)(?:\|[^\]]*?)?\]\]", sets_section):
            name = m.group(1).strip()
            # 세트 관련 링크만 (Sets 카테고리 등 제외)
            if not name.startswith("Category:") and not name.startswith("File:"):
                sets.append(name)

    # {{ESO Set Table| 패턴도 체크
    for m in re.finditer(r"\{\{ESO Set Table\|([^}|]+)", wikitext):
        name = m.group(1).strip()
        if name:
            sets.append(name)

    # 중복 제거 (순서 유지)
    seen = set()
    unique = []
    for s in sets:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return 0
