"""
하이브리드 Lore 검색 — 벡터 유사도 + BM25 + RRF + 선택적 Reranker.
"""
from __future__ import annotations

import logging

from pipeline.db import search_lore_fts

_LOG = logging.getLogger(__name__)

_RRF_K = 60  # Reciprocal Rank Fusion 상수


def search_lore(
    query: str,
    cfg: dict,
    *,
    limit: int = 5,
    use_reranker: bool = True,
) -> list[dict]:
    """하이브리드 Lore 검색.

    1. 벡터 검색 (LanceDB) → top-20
    2. BM25 검색 (FTS5) → top-20
    3. RRF 병합
    4. (선택) Voyage Reranker
    5. top-{limit} 반환

    Fallback: 벡터 DB 없으면 BM25만, API 키 없으면 BM25만.
    """
    candidates: dict[int, dict] = {}  # chunk_id → {page_title, section, text, rrf_score}

    # 1. 벡터 검색
    vector_hits = _vector_search(query, cfg, limit=20)
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

    # 2. BM25 검색
    bm25_hits = _bm25_search(query, limit=20)
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

    # 4. 선택적 Reranker
    if use_reranker and len(ranked) > limit:
        ranked = _rerank(query, ranked, cfg, limit=limit)
    else:
        ranked = ranked[:limit]

    # 최종 score 필드 추가
    for r in ranked:
        r["score"] = r.get("rerank_score", r.get("rrf_score", 0.0))

    return ranked


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
