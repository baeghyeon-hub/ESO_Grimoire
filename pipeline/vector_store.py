"""
LanceDB 벡터 스토어 — Lore 청크 임베딩 저장/검색.

파일 기반 벡터 DB (서버 불필요, PyInstaller 호환).
"""
from __future__ import annotations

import logging
import os
import sys

import lancedb
import pyarrow as pa

_LOG = logging.getLogger(__name__)

_DB_DIR = "lore.lance"
_TABLE_NAME = "lore_chunks"

# Voyage 4 = 1024차원
_VECTOR_DIM = 1024

_SCHEMA = pa.schema([
    pa.field("chunk_id", pa.int64()),
    pa.field("page_title", pa.utf8()),
    pa.field("section", pa.utf8()),
    pa.field("text", pa.utf8()),
    pa.field("vector", pa.list_(pa.float32(), _VECTOR_DIM)),
])


def _lance_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "db", _DB_DIR)


def _get_db() -> lancedb.DBConnection:
    path = _lance_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return lancedb.connect(path)


def get_table() -> lancedb.table.Table:
    """lore_chunks 테이블 open/create."""
    db = _get_db()
    if _TABLE_NAME in db.table_names():
        return db.open_table(_TABLE_NAME)
    return db.create_table(_TABLE_NAME, schema=_SCHEMA)


def upsert_embeddings(records: list[dict]) -> int:
    """임베딩 레코드 삽입/갱신.

    각 record: {chunk_id, page_title, section, text, vector}
    """
    if not records:
        return 0
    table = get_table()
    table.add(records)
    return len(records)


def search_vectors(query_vector: list[float], limit: int = 20) -> list[dict]:
    """벡터 유사도 검색."""
    table = get_table()
    try:
        results = (
            table.search(query_vector)
            .limit(limit)
            .to_list()
        )
        return results
    except Exception as e:
        _LOG.warning("[vector_store] search failed: %s", e)
        return []


def get_stats() -> dict:
    """테이블 통계."""
    try:
        table = get_table()
        return {"count": table.count_rows()}
    except Exception:
        return {"count": 0}


def is_ready() -> bool:
    """벡터 스토어에 데이터가 있는지 확인."""
    try:
        stats = get_stats()
        return stats["count"] > 0
    except Exception:
        return False
