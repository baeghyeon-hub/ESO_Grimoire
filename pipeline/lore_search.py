"""
하이브리드 Lore 검색 — 벡터 유사도 + BM25 + RRF + 선택적 Reranker.
"""
from __future__ import annotations

import logging
import re

from pipeline.db import search_lore_fts

_LOG = logging.getLogger(__name__)

_RRF_K = 60  # Reciprocal Rank Fusion 상수

# ── 쿼리 확장: 한국어/약어 → 영어 매핑 ──────────────────
_QUERY_ALIASES = {
    # 한국어 → 영어
    "드웨머": "Dwemer", "드워프": "Dwemer",
    "아카토쉬": "Akatosh", "아카토시": "Akatosh",
    "몰라그 발": "Molag Bal", "몰라그발": "Molag Bal",
    "데이드라": "Daedric Princes Daedra",
    "데이드릭": "Daedric",
    "탈모어": "Thalmor", "알드메리": "Aldmeri Dominion",
    "타이버 셉팀": "Tiber Septim", "탈로스": "Talos",
    "비벡": "Vivec", "네레바르": "Nerevar",
    "쉐오고라스": "Sheogorath", "쉐오고라스": "Sheogorath",
    "허마이오스 모라": "Hermaeus Mora",
    "메리디아": "Meridia", "아주라": "Azura",
    "보에디아": "Boethiah", "메팔라": "Mephala",
    "로칸": "Lorkhan", "로르칸": "Lorkhan",
    "너크로맨서": "Necromancer", "네크로맨서": "Necromancer",
    "뱀파이어": "Vampire", "늑대인간": "Werewolf Lycanthropy",
    "다크 앵커": "Dark Anchor Dolmen",
    "콜드하버": "Coldharbour",
    # 약어
    "cp": "Champion Points",
    "wb": "World Boss",
    "hm": "Hard Mode",
    "dsa": "Dragonstar Arena",
    "vma": "Vateshran Hollows Maelstrom Arena",
    "vdsr": "Dreadsail Reef",
    "vss": "Sunspire",
    "vcr": "Cloudrest",
}


def _expand_query(query: str) -> str:
    """한국어/약어 쿼리를 영어로 확장. 원본도 유지."""
    expanded = query
    lower = query.lower().strip()

    # 정확히 매칭
    if lower in _QUERY_ALIASES:
        expanded = f"{query} {_QUERY_ALIASES[lower]}"
        return expanded

    # 부분 매칭
    for ko, en in _QUERY_ALIASES.items():
        if ko in lower:
            expanded = f"{query} {en}"
            break

    return expanded


def search_lore(
    query: str,
    cfg: dict,
    *,
    limit: int = 5,
    use_reranker: bool = True,
) -> list[dict]:
    """하이브리드 Lore 검색.

    1. 쿼리 확장 (한국어/약어 → 영어)
    2. 벡터 검색 (LanceDB) → top-30
    3. BM25 검색 (FTS5) → top-30 (원본 + 확장 쿼리)
    4. RRF 병합
    5. (선택) Voyage Reranker → top-{limit}

    Fallback: 벡터 DB 없으면 BM25만, API 키 없으면 BM25만.
    """
    expanded = _expand_query(query)
    if expanded != query:
        _LOG.info("[lore_search] query expanded: %r -> %r", query, expanded)

    candidates: dict[int, dict] = {}  # chunk_id → {page_title, section, text, rrf_score}

    # 1. 벡터 검색 (원본 쿼리 — 벡터는 의미 기반이라 확장 불필요)
    vector_hits = _vector_search(query, cfg, limit=30)
    for rank, hit in enumerate(vector_hits):
        cid = hit.get("chunk_id", 0)
        if cid not in candidates:
            candidates[cid] = {
                "chunk_id": cid,
                "page_title": hit.get("page_title", ""),
                "section": hit.get("section", ""),
                "text": hit.get("text", ""),
                "rrf_score": 0.0,
                "sources": [],
            }
        candidates[cid]["rrf_score"] += 1.0 / (_RRF_K + rank + 1)
        candidates[cid]["sources"].append("vector")

    # 2. BM25 검색 — 확장된 쿼리로 (키워드 매칭이라 확장 효과 큼)
    bm25_query = expanded if expanded != query else query
    bm25_hits = _bm25_search(bm25_query, limit=30)
    for rank, hit in enumerate(bm25_hits):
        cid = hit.get("id", 0)
        if cid not in candidates:
            candidates[cid] = {
                "chunk_id": cid,
                "page_title": hit.get("page_title", ""),
                "section": hit.get("section", ""),
                "text": hit.get("snippet", ""),
                "rrf_score": 0.0,
                "sources": [],
            }
        candidates[cid]["rrf_score"] += 1.0 / (_RRF_K + rank + 1)
        candidates[cid]["sources"].append("bm25")

    if not candidates:
        return []

    # 3. RRF 정렬
    ranked = sorted(candidates.values(), key=lambda x: -x["rrf_score"])

    # 전체 텍스트 보강 (BM25는 snippet만 가지고 있을 수 있으므로)
    ranked = _enrich_texts(ranked)

    # 4. 중복 제거 — 같은 page_title의 청크가 너무 많으면 다양성 ↓
    ranked = _diversify(ranked, max_per_page=3)

    # 5. 선택적 Reranker
    rerank_pool = min(len(ranked), limit * 3)  # 리랭커에 더 많은 후보 제공
    if use_reranker and len(ranked) > limit:
        ranked = _rerank(query, ranked[:rerank_pool], cfg, limit=limit)
    else:
        ranked = ranked[:limit]

    # 최종 score 필드 추가
    for r in ranked:
        r["score"] = r.get("rerank_score", r.get("rrf_score", 0.0))

    return ranked


def _diversify(candidates: list[dict], max_per_page: int = 3) -> list[dict]:
    """같은 page_title에서 최대 max_per_page개만 유지."""
    page_counts: dict[str, int] = {}
    result = []
    overflow = []

    for c in candidates:
        title = c.get("page_title", "")
        count = page_counts.get(title, 0)
        if count < max_per_page:
            result.append(c)
            page_counts[title] = count + 1
        else:
            overflow.append(c)

    # overflow는 뒤에 추가 (리랭커가 재평가할 수 있도록)
    return result + overflow


def _vector_search(query: str, cfg: dict, limit: int = 20) -> list[dict]:
    """벡터 유사도 검색 (Voyage + LanceDB)."""
    try:
        from pipeline.vector_store import is_ready, search_vectors
        from pipeline.embedder import embed_query

        if not is_ready():
            return []

        voyage_key = cfg.get("voyage", {}).get("api_key", "")
        if not voyage_key:
            return []

        query_vec = embed_query(query, cfg)
        return search_vectors(query_vec, limit=limit)
    except Exception as e:
        _LOG.warning("[lore_search] vector search failed: %s", e)
        return []


def _bm25_search(query: str, limit: int = 20) -> list[dict]:
    """BM25 전문 검색 (FTS5)."""
    try:
        return search_lore_fts(query, limit=limit)
    except Exception as e:
        _LOG.warning("[lore_search] BM25 search failed: %s", e)
        return []


def _enrich_texts(candidates: list[dict]) -> list[dict]:
    """BM25 결과의 snippet을 전체 텍스트로 교체."""
    from pipeline.db import _get_conn

    # BM25 소스가 포함된 항목은 항상 전체 텍스트로 교체 (snippet에 하이라이트 마커 포함)
    ids_needing_text = [c["chunk_id"] for c in candidates if "bm25" in c.get("sources", [])]
    if not ids_needing_text:
        return candidates

    conn = _get_conn()
    placeholders = ",".join("?" * len(ids_needing_text))
    rows = conn.execute(
        f"SELECT id, chunk_text FROM lore_chunks WHERE id IN ({placeholders})",
        ids_needing_text,
    ).fetchall()
    text_map = {r["id"]: r["chunk_text"] for r in rows}

    for c in candidates:
        if c["chunk_id"] in text_map:
            c["text"] = text_map[c["chunk_id"]]

    return candidates


def _rerank(query: str, candidates: list[dict], cfg: dict, limit: int) -> list[dict]:
    """Voyage Reranker로 리랭킹."""
    try:
        import voyageai

        api_key = cfg.get("voyage", {}).get("api_key", "")
        if not api_key:
            return candidates[:limit]

        model = cfg.get("voyage", {}).get("rerank_model", "rerank-2.5")
        client = voyageai.Client(api_key=api_key)

        documents = [c["text"][:2000] for c in candidates]  # 리랭커 입력 제한

        result = client.rerank(
            query=query,
            documents=documents,
            model=model,
            top_k=limit,
        )

        reranked = []
        for r in result.results:
            idx = r.index
            cand = candidates[idx].copy()
            cand["rerank_score"] = r.relevance_score
            reranked.append(cand)

        return reranked

    except Exception as e:
        _LOG.warning("[lore_search] reranker failed: %s", e)
        return candidates[:limit]
