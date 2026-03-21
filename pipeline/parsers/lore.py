"""
Lore 파서 — Lore 네임스페이스 페이지를 섹션 기반 청크로 분할.

구조화된 데이터가 아닌 서사/백과사전형 텍스트를 처리.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pipeline.parsers.common import clean_wikitext_inline, get_intro


@dataclass
class LoreChunk:
    page_title: str     # "Lore:Akatosh"
    section: str        # "Introduction", "Worship", "History"
    text: str           # 정제된 plain text
    token_count: int    # 대략 추정


# 최소/최대 청크 크기 (토큰 추정치 기준)
_MIN_CHUNK_TOKENS = 60
_MAX_CHUNK_TOKENS = 1500
_MERGE_THRESHOLD = 200  # 이 미만이면 다음 섹션과 병합


def parse_lore_page(title: str, wikitext: str) -> list[LoreChunk]:
    """Lore 페이지를 섹션 기반 청크로 분할."""
    if wikitext.strip().upper().startswith("#REDIRECT"):
        return []

    # Lore 전용 정제
    cleaned = _clean_lore_wikitext(wikitext)

    chunks: list[LoreChunk] = []

    # 인트로 (첫 ==헤딩== 이전)
    intro = get_intro(cleaned)
    intro_text = _clean_text(intro)
    if intro_text and _estimate_tokens(intro_text) >= _MIN_CHUNK_TOKENS:
        chunks.append(LoreChunk(
            page_title=title,
            section="Introduction",
            text=intro_text,
            token_count=_estimate_tokens(intro_text),
        ))

    # ==Level 2== 섹션별 추출
    sections = _split_sections(cleaned)
    pending_name = ""
    pending_text = ""

    for sec_name, sec_text in sections:
        text = _clean_text(sec_text)
        if not text:
            continue

        tokens = _estimate_tokens(text)

        # 병합 대상: 너무 짧은 섹션
        if tokens < _MERGE_THRESHOLD:
            if pending_text:
                pending_text += f"\n\n{sec_name}: {text}"
                pending_name += f" / {sec_name}"
            else:
                pending_name = sec_name
                pending_text = text
            continue

        # 이전 pending flush
        if pending_text:
            _flush_chunk(chunks, title, pending_name, pending_text)
            pending_name = ""
            pending_text = ""

        # 너무 긴 섹션: 문단 경계에서 분할
        if tokens > _MAX_CHUNK_TOKENS:
            _split_long_section(chunks, title, sec_name, text)
        else:
            chunks.append(LoreChunk(
                page_title=title,
                section=sec_name,
                text=text,
                token_count=tokens,
            ))

    # 남은 pending flush
    if pending_text:
        _flush_chunk(chunks, title, pending_name, pending_text)

    return chunks


def _flush_chunk(chunks: list[LoreChunk], title: str, name: str, text: str):
    tokens = _estimate_tokens(text)
    if tokens >= _MIN_CHUNK_TOKENS:
        chunks.append(LoreChunk(
            page_title=title, section=name, text=text, token_count=tokens,
        ))


def _split_long_section(chunks: list[LoreChunk], title: str, sec_name: str, text: str):
    """긴 섹션을 문단 경계에서 분할."""
    paragraphs = re.split(r"\n\s*\n", text)
    current = ""
    part = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and _estimate_tokens(current + "\n\n" + para) > _MAX_CHUNK_TOKENS:
            # 현재 청크 저장
            chunk_name = f"{sec_name} (part {part})" if part > 1 or len(paragraphs) > 2 else sec_name
            tokens = _estimate_tokens(current)
            if tokens >= _MIN_CHUNK_TOKENS:
                chunks.append(LoreChunk(
                    page_title=title, section=chunk_name, text=current, token_count=tokens,
                ))
            part += 1
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunk_name = f"{sec_name} (part {part})" if part > 1 else sec_name
        tokens = _estimate_tokens(current)
        if tokens >= _MIN_CHUNK_TOKENS:
            chunks.append(LoreChunk(
                page_title=title, section=chunk_name, text=current, token_count=tokens,
            ))


def _split_sections(wikitext: str) -> list[tuple[str, str]]:
    """==Level 2== 섹션을 (heading, content) 쌍으로 분할."""
    sections = []
    pattern = re.compile(r"^==\s*([^=]+?)\s*==\s*$", re.MULTILINE)
    matches = list(pattern.finditer(wikitext))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        content = wikitext[start:end].strip()
        # 갤러리, 참조, 카테고리 등 스킵
        if heading.lower() in ("gallery", "see also", "references", "notes",
                                "external links", "bugs", "images"):
            continue
        sections.append((heading, content))

    return sections


def _clean_lore_wikitext(wikitext: str) -> str:
    """Lore 전용 wikitext 정제 (clean_wikitext_inline 이전 단계)."""
    text = wikitext
    # {{Lore Link|display|target}} → display
    text = re.sub(r"\{\{Lore Link\|([^|}]+)(?:\|[^}]*)?\}\}", r"\1", text)
    # {{Cite Book|...}} 제거
    text = re.sub(r"\{\{Cite Book\|[^}]*\}\}", "", text)
    # {{Main|...}} → (see: ...)
    text = re.sub(r"\{\{Main\|([^}]+)\}\}", r"(see: \1)", text)
    # {{Anchor|...}} 제거
    text = re.sub(r"\{\{Anchor\|[^}]*\}\}", "", text)
    # <ref>...</ref> 제거
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*/?>", "", text)
    # 카테고리 태그 제거
    text = re.sub(r"\[\[Category:[^\]]*\]\]", "", text)
    return text


def _clean_text(text: str) -> str:
    """최종 텍스트 정제."""
    text = clean_wikitext_inline(text)
    # 서브 헤딩 마크업 제거
    text = re.sub(r"^={3,}\s*([^=]+?)\s*={3,}\s*$", r"\1:", text, flags=re.MULTILINE)
    # 연속 빈 줄 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _estimate_tokens(text: str) -> int:
    """대략적 토큰 수 추정 (단어 수 × 1.3)."""
    return int(len(text.split()) * 1.3)
