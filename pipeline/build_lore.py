"""
Lore pipeline master script — crawl -> chunk -> embed in one run.

Usage:
    python -m pipeline.build_lore              # full run (incremental)
    python -m pipeline.build_lore --step crawl  # crawl only
    python -m pipeline.build_lore --step chunk  # chunk only
    python -m pipeline.build_lore --step embed  # embed only
    python -m pipeline.build_lore --force       # full reprocess
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
_LOG = logging.getLogger(__name__)


def _step_crawl(cfg: dict, *, limit: int = 0):
    """Step 1: Lore crawling."""
    from pipeline.crawler import UESPCrawler, LORE_CATEGORIES
    from pipeline.db import _get_conn

    conn = _get_conn()
    before = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE category LIKE 'lore-%'"
    ).fetchone()[0]

    crawler = UESPCrawler(delay=0.3)
    total_saved = 0
    total_cats = len(LORE_CATEGORIES)

    for i, (cat_key, cat_name) in enumerate(LORE_CATEGORIES.items(), 1):
        existing = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE category = ?", (cat_key,)
        ).fetchone()[0]
        print(f"\n[{i}/{total_cats}] {cat_key} (existing: {existing})")

        saved = crawler.crawl_lore_category(
            cat_key, limit=limit, skip_existing=True,
            progress_fn=lambda cur, total, title: print(
                f"  [{cur}/{total}] {title}"
            ) if cur % 100 == 0 or cur == total else None,
        )
        total_saved += saved
        print(f"  -> {saved} new pages saved")

    after = conn.execute(
        "SELECT COUNT(*) FROM pages WHERE category LIKE 'lore-%'"
    ).fetchone()[0]
    print(f"\nCrawling done: {before} -> {after} pages (+{after - before})")
    return after


def _step_chunk(*, force: bool = False):
    """Step 2: Lore chunking."""
    from pipeline.lore_chunker import chunk_lore_pages
    from pipeline.db import _get_conn

    def progress(cur, total, title):
        if cur % 200 == 0 or cur == total:
            print(f"  [{cur}/{total}] {title}")

    count = chunk_lore_pages(force=force, progress_fn=progress)

    conn = _get_conn()
    r = conn.execute(
        "SELECT COUNT(*) as cnt, COALESCE(AVG(token_count), 0) as avg_tok, "
        "COALESCE(SUM(token_count), 0) as total_tok FROM lore_chunks"
    ).fetchone()
    print(f"\nChunking done: {r['cnt']} chunks, avg {r['avg_tok']:.0f} tokens, total {r['total_tok']:,.0f} tokens")
    return count


def _step_embed(cfg: dict):
    """Step 3: Voyage embedding."""
    from pipeline.embedder import embed_pending_chunks

    voyage_key = cfg.get("voyage", {}).get("api_key", "")
    if not voyage_key:
        print("WARNING: No Voyage API key — set voyage.api_key in config.json.")
        print("  BM25 search works without embeddings.")
        return 0

    model = cfg.get("voyage", {}).get("embed_model", "voyage-4")
    print(f"Model: {model}")

    def progress(done, total):
        pct = done * 100 // total if total else 0
        print(f"  [{done}/{total}] {pct}% embedded")

    t0 = time.time()
    count = embed_pending_chunks(cfg, progress_fn=progress)
    elapsed = time.time() - t0

    if count > 0:
        print(f"\nEmbedding done: {count} chunks, {elapsed:.1f}s elapsed")

        from pipeline.vector_store import get_stats
        stats = get_stats()
        print(f"LanceDB total vectors: {stats['count']}")
    else:
        print("No new chunks to embed (all done)")

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Lore pipeline: crawl -> chunk -> embed"
    )
    parser.add_argument(
        "--step",
        choices=["crawl", "chunk", "embed"],
        default=None,
        help="Run specific step only (default: all)",
    )
    parser.add_argument("--force", action="store_true", help="Full reprocess")
    parser.add_argument("--limit", type=int, default=0, help="Crawl page limit (0=all)")
    args = parser.parse_args()

    from core.config import load_config
    from pipeline.db import init_db

    cfg = load_config()
    init_db()

    steps = [args.step] if args.step else ["crawl", "chunk", "embed"]

    print("=" * 50)
    print("Grimoire Lore Pipeline")
    print("=" * 50)

    if "crawl" in steps:
        print("\n> Step 1/3: Crawling")
        _step_crawl(cfg, limit=args.limit)

    if "chunk" in steps:
        print("\n> Step 2/3: Chunking")
        _step_chunk(force=args.force)

    if "embed" in steps:
        print("\n> Step 3/3: Embedding")
        _step_embed(cfg)

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
