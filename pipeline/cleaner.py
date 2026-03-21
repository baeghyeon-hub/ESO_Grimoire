"""
Wikitext Cleaner — 원본 wikitext를 정제된 plain text로 변환.

1단계: 섹션 분리 (intro, bonuses, pieces, drop_locations, notes)
2단계: 마크업 제거 (템플릿, HTML, 위키링크 → plain text)
3단계: 구조화 메타 추출 (Item Link 목록 등)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CleanedPage:
    """정제된 페이지 데이터."""
    title: str
    intro: str = ""          # 첫 문단 (세트 설명)
    bonuses: str = ""         # 보너스 섹션 (정제 텍스트)
    pieces: str = ""          # 피스 정보
    drop_locations: str = ""  # 드랍 위치
    notes: str = ""           # 기타 노트
    plain_text: str = ""      # 전체 정제 텍스트 (FTS용)
    unique_pieces: list[str] = field(default_factory=list)  # 유니크 아이템 이름


# ── 섹션 분리 ────────────────────────────────────────────

_SECTION_RE = re.compile(r"^(={2,3})\s*(.+?)\s*\1\s*$", re.MULTILINE)


def _split_sections(wikitext: str) -> dict[str, str]:
    """wikitext를 섹션별로 분리."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(wikitext))

    # 인트로 (첫 섹션 이전)
    if matches:
        sections["intro"] = wikitext[:matches[0].start()].strip()
    else:
        sections["intro"] = wikitext.strip()

    # 각 섹션
    for i, m in enumerate(matches):
        name = m.group(2).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        sections[name] = wikitext[start:end].strip()

    return sections


# ── 마크업 정제 ──────────────────────────────────────────

def _clean_templates(text: str) -> str:
    """위키 템플릿 제거/변환."""
    # {{Trail|...}}, {{Online Update|...}}, {{Mod Header|...}} 등 완전 제거
    text = re.sub(r"\{\{(?:Trail|Online Update|Mod Header|Online Sets|"
                  r"ESO Sets With|icon|about|ON:Overland Sets|"
                  r"ON:Dungeon Sets)[^}]*\}\}", "", text, flags=re.IGNORECASE)

    # {{Item Link|id=...|Name|quality=...|summary=...}} → Name
    text = re.sub(
        r"\{\{Item Link\|(?:[^|}]*\|)*?([^|}]+?)(?:\|quality=[^}]*)?\}\}",
        r"\1", text
    )

    # {{ESO Type Link|value|suffix}} → value Type suffix
    text = re.sub(r"\{\{ESO (\w+) (?:Link|Damage Link)(?:\|([^}]*))?\}\}",
                  _expand_eso_template, text)

    # {{ESO Spell/Weapon Damage Link}} → Spell/Weapon Damage
    text = re.sub(r"\{\{ESO (Spell|Weapon) Damage Link[^}]*\}\}", r"\1 Damage", text)

    # {{Place Link|Name}} → Name
    text = re.sub(r"\{\{Place Link\|([^}|]+)[^}]*\}\}", r"\1", text)

    # {{ESO Quality Color|...|Name}} → Name
    text = re.sub(r"\{\{ESO Quality Color\|[^|]*\|([^}]*)\}\}", r"\1", text)

    # {{ESO DLC|Name}} → Name DLC
    text = re.sub(r"\{\{ESO DLC\|([^}]*)\}\}", r"\1", text)

    # {{ESO Champion|N}} → CP N
    text = re.sub(r"\{\{ESO Champion\|(\d+)\}\}", r"CP \1", text)

    # 남은 모든 템플릿 제거
    text = re.sub(r"\{\{[^}]*\}\}", "", text)

    return text


def _expand_eso_template(m: re.Match) -> str:
    """ESO Link 템플릿 확장 (cleaner 전용)."""
    stat_type = m.group(1)
    params_str = m.group(2) or ""
    params = [p.strip() for p in params_str.split("|") if p.strip() and p.strip() != "y"]

    if not params:
        return stat_type

    value = params[0] if re.match(r"[\d\-\.%]", params[0]) else ""
    suffix = ""
    for p in params:
        if p in ("Maximum", "Recovery"):
            suffix = p
        elif not re.match(r"[\d\-\.%]", p) and p not in ("y", ""):
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


def _clean_wikilinks(text: str) -> str:
    """위키링크를 표시 텍스트로 변환."""
    # [[ON:Page|Display]] → Display
    text = re.sub(r"\[\[(?:ON:|Online:)?[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    # [[ON:Page]] → Page
    text = re.sub(r"\[\[(?:ON:|Online:)?([^\]]*)\]\]", r"\1", text)
    return text


def _clean_html(text: str) -> str:
    """HTML 태그 제거."""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<onlyinclude>|</onlyinclude>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def _clean_formatting(text: str) -> str:
    """위키 서식 정리."""
    # __NOTOC__ 등
    text = re.sub(r"__[A-Z]+__", "", text)
    # '''bold''' → bold
    text = re.sub(r"'{2,3}(.+?)'{2,3}", r"\1", text)
    # ---- (수평선)
    text = re.sub(r"^-{4,}\s*$", "", text, flags=re.MULTILINE)
    # 여러 빈 줄 → 하나
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_unique_pieces(pieces_text: str) -> list[str]:
    """Pieces 섹션에서 유니크 아이템 이름 추출."""
    items = []
    # {{Item Link|id=...|Name|...}} 패턴
    for m in re.finditer(r"\{\{Item Link\|(?:[^|}]*\|)*?([^|}]+?)(?:\|quality=[^}]*)?\}\}", pieces_text):
        name = m.group(1).strip()
        if name and not name.startswith("id="):
            items.append(name)
    return items


def clean_wikitext(text: str) -> str:
    """wikitext → 정제된 plain text (단일 함수)."""
    text = _clean_templates(text)
    text = _clean_wikilinks(text)
    text = _clean_html(text)
    text = _clean_formatting(text)
    return text


# ── 메인 함수 ────────────────────────────────────────────

def clean_page(title: str, wikitext: str) -> CleanedPage:
    """wikitext를 섹션별로 분리하고 정제."""
    sections = _split_sections(wikitext)
    result = CleanedPage(title=title)

    # 유니크 피스 추출 (정제 전에)
    if "pieces" in sections:
        result.unique_pieces = _extract_unique_pieces(sections["pieces"])

    # 각 섹션 정제
    result.intro = clean_wikitext(sections.get("intro", ""))
    result.bonuses = clean_wikitext(sections.get("bonuses", ""))
    result.pieces = clean_wikitext(sections.get("pieces", ""))
    result.drop_locations = clean_wikitext(sections.get("drop locations", ""))
    result.notes = clean_wikitext(sections.get("notes", ""))

    # 전체 plain text (FTS용)
    all_parts = [result.intro, result.bonuses, result.pieces,
                 result.drop_locations, result.notes]
    result.plain_text = "\n\n".join(p for p in all_parts if p)

    return result
