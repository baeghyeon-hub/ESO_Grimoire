"""
Hybrid Search — FTS5 후보 + 점수 기반 리랭킹.

1단계: FTS5로 후보 20개 추출 (빠른 키워드 매칭)
2단계: 각 후보에 점수 부여 (제목 매칭, 세트 매칭, stat 매칭 등)
3단계: 점수 순으로 정렬하여 상위 N개 반환
"""
from __future__ import annotations

import logging
import re

_LOG = logging.getLogger(__name__)


def hybrid_search(query: str, limit: int = 10) -> list[dict]:
    """FTS 후보 추출 + scoring 리랭킹."""
    from pipeline.db import _get_conn

    conn = _get_conn()
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    # 1단계: FTS5로 넓게 후보 추출
    fts_candidates = _fts_search(conn, query, limit=30)

    # 세트 테이블에서도 후보 추출 (이름 매칭)
    set_candidates = _set_name_search(conn, query, limit=20)

    # stat 기반 후보 추출
    stat_candidates = _stat_search(conn, query_words, limit=20)

    # 후보 병합 (중복 제거)
    merged = {}
    for c in fts_candidates + set_candidates + stat_candidates:
        key = c.get("title") or c.get("name", "")
        if key and key not in merged:
            merged[key] = c

    # 2단계: 각 후보에 점수 부여
    scored = []
    for key, c in merged.items():
        score = _score_candidate(c, query_lower, query_words)
        c["_score"] = score
        scored.append(c)

    # 3단계: 점수 순 정렬
    scored.sort(key=lambda x: x["_score"], reverse=True)

    return scored[:limit]


def _fts_search(conn, query: str, limit: int = 30) -> list[dict]:
    """FTS5 전문 검색."""
    try:
        rows = conn.execute(
            """
            SELECT p.title, p.clean_text,
                   snippet(pages_fts, 1, '', '', '...', 60) AS snippet,
                   rank
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        _LOG.warning("FTS search failed: %s", e)
        return []


def _set_name_search(conn, query: str, limit: int = 20) -> list[dict]:
    """세트 이름 LIKE 검색."""
    rows = conn.execute(
        """
        SELECT s.name AS title, s.set_type, s.armor_type, s.location,
               s.description AS snippet
        FROM sets s
        WHERE s.name LIKE ? COLLATE NOCASE
        ORDER BY s.name
        LIMIT ?
        """,
        (f"%{query}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def _stat_search(conn, query_words: set[str], limit: int = 20) -> list[dict]:
    """쿼리 단어에서 stat 키워드를 감지하여 관련 세트 검색."""
    stat_keywords = {
        "crit": "Critical Chance",
        "critical": "Critical Chance",
        "penetration": "Offensive Penetration",
        "pen": "Offensive Penetration",
        "weapon damage": "Weapon Damage",
        "spell damage": "Spell Damage",
        "magicka": "Maximum Magicka",
        "stamina": "Maximum Stamina",
        "health": "Maximum Health",
        "recovery": "Recovery",
        "armor": "Armor",
        "healing": "Healing",
    }

    detected_stats = []
    query_str = " ".join(query_words)
    for keyword, stat_type in stat_keywords.items():
        if keyword in query_str:
            detected_stats.append(stat_type)

    if not detected_stats:
        return []

    results = []
    for stat in detected_stats[:2]:  # 최대 2개 stat
        rows = conn.execute(
            """
            SELECT DISTINCT s.name AS title, s.set_type, s.armor_type,
                   s.location, b.bonus_text AS snippet
            FROM sets s
            JOIN set_bonuses b ON s.id = b.set_id
            WHERE b.stat_type LIKE ? COLLATE NOCASE
            LIMIT ?
            """,
            (f"%{stat}%", limit),
        ).fetchall()
        results.extend(dict(r) for r in rows)

    return results


def _score_candidate(candidate: dict, query_lower: str, query_words: set[str]) -> float:
    """후보에 관련도 점수 부여."""
    score = 0.0
    title = (candidate.get("title") or "").lower()
    snippet = (candidate.get("snippet") or "").lower()

    # 제목 정확 매칭 (최고 점수)
    clean_title = title.replace("online:", "").strip()
    if clean_title == query_lower:
        score += 100
    elif query_lower in clean_title:
        score += 50
    elif clean_title in query_lower:
        score += 30

    # 제목에 쿼리 단어 포함
    for word in query_words:
        if word in clean_title:
            score += 10

    # 세트 데이터 보너스 (구조화된 데이터가 있으면 더 유용)
    if candidate.get("set_type"):
        score += 5
    if candidate.get("armor_type"):
        score += 3

    # FTS rank (있으면)
    fts_rank = candidate.get("rank")
    if fts_rank is not None:
        # FTS rank는 음수 (더 작을수록 좋음), 정규화
        score += max(0, 20 + fts_rank * 2)

    # 스니펫에 쿼리 단어 포함
    for word in query_words:
        if word in snippet:
            score += 2

    return score
