"""
Lore 청커 — Lore 페이지를 lore_chunks 테이블로 변환.

crawl → chunk → embed 파이프라인의 두 번째 단계.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from pipeline.db import get_db, init_db
from pipeline.parsers.lore import parse_lore_page

_LOG = logging.getLogger(__name__)


def chunk_lore_pages(*, force: bool = False, progress_fn=None) -> int:
    """모든 Lore 페이지를 파싱하여 lore_chunks에 저장.

    Args:
        force: True면 이미 파싱된 페이지도 다시 처리
        progress_fn: 진행 콜백 fn(current, total, title)

    Returns:
        생성된 청크 수
    """
    init_db()

    with get_db() as conn:
        if force:
            rows = conn.execute(
                "SELECT id, title, wikitext FROM pages WHERE category LIKE 'lore-%'"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, wikitext FROM pages WHERE category LIKE 'lore-%' AND parsed_at IS NULL"
            ).fetchall()

    total = len(rows)
    _LOG.info("[chunker] %d lore pages to process", total)
    total_chunks = 0

    for i, row in enumerate(rows):
        page_id = row["id"]
        title = row["title"]
        wikitext = row["wikitext"]

        if progress_fn:
            progress_fn(i + 1, total, title)

        chunks = parse_lore_page(title, wikitext)
        if not chunks:
            # parsed_at만 갱신
            with get_db() as conn:
                conn.execute(
                    "UPDATE pages SET parsed_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), page_id),
                )
            continue

        with get_db() as conn:
            # 기존 청크 삭제 (해당 페이지)
            conn.execute("DELETE FROM lore_chunks WHERE page_title = ?", (title,))

            for chunk in chunks:
                chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
                conn.execute(
                    """INSERT INTO lore_chunks (page_title, section, chunk_text, chunk_hash, token_count)
                       VALUES (?, ?, ?, ?, ?)""",
                    (chunk.page_title, chunk.section, chunk.text,
                     chunk_hash, chunk.token_count),
                )

            conn.execute(
                "UPDATE pages SET parsed_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), page_id),
            )

        total_chunks += len(chunks)

    _LOG.info("[chunker] %d chunks created from %d pages", total_chunks, total)
    return total_chunks


# ── CLI ───────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Lore Chunker")
    parser.add_argument("--force", action="store_true", help="이미 파싱된 페이지도 다시 처리")
    args = parser.parse_args()

    def progress(cur, total, title):
        if cur % 100 == 0 or cur == total:
            print(f"  [{cur}/{total}] {title}")

    total = chunk_lore_pages(force=args.force, progress_fn=progress)
    print(f"Total chunks: {total}")


if __name__ == "__main__":
    main()
