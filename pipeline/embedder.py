"""
Voyage AI 임베딩 파이프라인 — lore_chunks를 벡터화하여 LanceDB에 저장.

crawl → chunk → embed 파이프라인의 마지막 단계.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from pipeline.db import get_db, init_db
from pipeline.vector_store import _VECTOR_DIM

_LOG = logging.getLogger(__name__)

_BATCH_SIZE = 128
_MAX_TOKENS_PER_BATCH = 100_000
_DELAY_BETWEEN_BATCHES = 0.5


def _get_voyage_client(cfg: dict):
    """Voyage API 클라이언트 생성."""
    import voyageai
    api_key = cfg.get("voyage", {}).get("api_key", "")
    if not api_key:
        raise ValueError("Voyage API key not configured. Set voyage.api_key in config.json")
    return voyageai.Client(api_key=api_key)


def embed_pending_chunks(cfg: dict, *, progress_fn=None) -> int:
    """미임베딩 청크를 Voyage API로 벡터화하여 LanceDB에 저장.

    Returns:
        임베딩된 청크 수
    """
    from pipeline.vector_store import upsert_embeddings

    init_db()

    model = cfg.get("voyage", {}).get("embed_model", "voyage-4")
    client = _get_voyage_client(cfg)

    # 미임베딩 청크 조회
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, page_title, section, chunk_text, token_count "
            "FROM lore_chunks WHERE embedded_at IS NULL "
            "ORDER BY id"
        ).fetchall()

    total = len(rows)
    if total == 0:
        _LOG.info("[embedder] no pending chunks")
        return 0

    _LOG.info("[embedder] %d chunks to embed (model: %s)", total, model)

    embedded = 0
    batch_rows = []
    batch_tokens = 0

    for i, row in enumerate(rows):
        batch_rows.append(row)
        batch_tokens += row["token_count"]

        # 배치 실행 조건: 크기 초과 또는 마지막
        is_last = (i == total - 1)
        batch_full = len(batch_rows) >= _BATCH_SIZE or batch_tokens >= _MAX_TOKENS_PER_BATCH

        if batch_full or is_last:
            count = _embed_batch(client, model, batch_rows)
            embedded += count

            if progress_fn:
                progress_fn(embedded, total)

            batch_rows = []
            batch_tokens = 0

            if not is_last:
                time.sleep(_DELAY_BETWEEN_BATCHES)

    _LOG.info("[embedder] %d chunks embedded", embedded)
    return embedded


def _embed_batch(client, model: str, rows: list) -> int:
    """단일 배치 임베딩 실행."""
    from pipeline.vector_store import upsert_embeddings

    texts = [r["chunk_text"] for r in rows]

    try:
        result = client.embed(texts, model=model, input_type="document", output_dimension=_VECTOR_DIM)
        vectors = result.embeddings
    except Exception as e:
        _LOG.error("[embedder] Voyage API error: %s", e)
        return 0

    # LanceDB 레코드 구성
    records = []
    for row, vec in zip(rows, vectors):
        records.append({
            "chunk_id": row["id"],
            "page_title": row["page_title"],
            "section": row["section"],
            "text": row["chunk_text"],
            "vector": vec,
        })

    upsert_embeddings(records)

    # SQLite embedded_at 갱신
    now = datetime.utcnow().isoformat()
    chunk_ids = [r["id"] for r in rows]
    with get_db() as conn:
        for cid in chunk_ids:
            conn.execute(
                "UPDATE lore_chunks SET embedded_at = ? WHERE id = ?",
                (now, cid),
            )

    return len(records)


def embed_query(query: str, cfg: dict) -> list[float]:
    """쿼리 텍스트를 임베딩 (검색용, input_type='query')."""
    model = cfg.get("voyage", {}).get("embed_model", "voyage-4")
    client = _get_voyage_client(cfg)
    result = client.embed([query], model=model, input_type="query", output_dimension=_VECTOR_DIM)
    return result.embeddings[0]


# ── CLI ───────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Voyage Embedder")
    parser.add_argument("--limit", type=int, default=0, help="최대 처리 청크 수 (0=전체)")
    args = parser.parse_args()

    from core.config import load_config
    cfg = load_config()

    def progress(done, total):
        print(f"  [{done}/{total}] embedded")

    count = embed_pending_chunks(cfg, progress_fn=progress)
    print(f"Total embedded: {count}")


if __name__ == "__main__":
    main()
