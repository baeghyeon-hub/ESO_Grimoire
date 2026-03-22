"""
Expanded pipeline — crawl new ESO/Lore categories -> chunk -> embed.

Usage:
    python -m pipeline.build_expanded              # full run
    python -m pipeline.build_expanded --step crawl  # crawl only
    python -m pipeline.build_expanded --step chunk  # chunk only
    python -m pipeline.build_expanded --step embed  # embed only
"""
from __future__ import annotations

import argparse
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
_LOG = logging.getLogger(__name__)

# 새로 추가할 ESO 카테고리 (구조화 테이블 없이 벡터 검색만)
NEW_ESO_CATEGORIES = [
    "achievements",      # 업적
    "antiquities",       # 고대유물
    "cp_passive",        # CP 패시브
    "cp_slotted",        # CP 슬롯
    "furnishings",       # 가구
    "recipes",           # 레시피
    "food",              # 음식
    "delves",            # 델브
    "public_dungeons",   # 공개 던전
    "factions",          # 팩션/길드
    "crown_store",       # 크라운 상점
    "mounts",            # 탈것
    "mementos",          # 메멘토
    "skill_styles",      # 스킬 스타일
    "classes",           # 클래스
    "items",             # 아이템
    "combat",            # 전투 시스템
    "armor",             # 방어구
    "races",             # 종족
    "events",            # 이벤트
    "activities",        # 활동
    "alliance_war",      # 얼라이언스 워
]

# 새로 추가할 Lore 카테고리
NEW_LORE_CATEGORIES = [
    "lore-appendices",   # 부록/용어
    "lore-disease",      # 질병
    "lore-calendar",     # 달력
    "lore-names",        # 이름 체계
    "lore-daedra",       # 데이드라
    "lore-archive",      # 로어마스터 아카이브
    "lore-undead",       # 언데드
    "lore-linguistics",  # 언어학
    "lore-spells",       # 주문
    "lore-empires",      # 제국
]


def _step_crawl(cfg: dict):
    """Step 1: 새 카테고리 크롤링."""
    from pipeline.crawler import UESPCrawler, LORE_CATEGORIES
    from pipeline.db import _get_conn

    crawler = UESPCrawler(delay=0.3)
    conn = _get_conn()
    total_saved = 0

    def progress(cur, total, title):
        if cur % 50 == 0 or cur == total:
            try:
                print(f"  [{cur}/{total}] {title}")
            except UnicodeEncodeError:
                print(f"  [{cur}/{total}] {title.encode('ascii', 'replace').decode()}")

    # ESO 카테고리
    print("\n--- ESO Categories ---")
    for cat in NEW_ESO_CATEGORIES:
        existing = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE category = ?", (cat,)
        ).fetchone()[0]
        print(f"\n> {cat} (existing: {existing})")

        saved = crawler.crawl_category(
            cat, skip_existing=True, progress_fn=progress,
        )
        total_saved += saved
        print(f"  -> {saved} new pages")

    # Lore 카테고리
    print("\n--- Lore Categories ---")
    for cat in NEW_LORE_CATEGORIES:
        existing = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE category = ?", (cat,)
        ).fetchone()[0]
        print(f"\n> {cat} (existing: {existing})")

        saved = crawler.crawl_lore_category(
            cat, skip_existing=True, progress_fn=progress,
        )
        total_saved += saved
        print(f"  -> {saved} new pages")

    print(f"\nCrawl total: {total_saved} new pages")
    return total_saved


def _step_chunk(*, force: bool = False):
    """Step 2: 새 페이지 청킹 (lore + ESO 확장 카테고리)."""
    from pipeline.lore_chunker import chunk_lore_pages
    from pipeline.db import _get_conn

    def progress(cur, total, title):
        if cur % 200 == 0 or cur == total:
            try:
                print(f"  [{cur}/{total}] {title}")
            except UnicodeEncodeError:
                print(f"  [{cur}/{total}] (encoding error)")

    count = chunk_lore_pages(force=force, progress_fn=progress)

    conn = _get_conn()
    r = conn.execute(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(token_count), 0) as total_tok "
        "FROM lore_chunks"
    ).fetchone()
    print(f"\nChunk total: {r['cnt']} chunks, {r['total_tok']:,} tokens")
    return count


def _step_embed(cfg: dict):
    """Step 3: 새 청크 voyage-4 임베딩."""
    from pipeline.embedder import embed_pending_chunks

    voyage_key = cfg.get("voyage", {}).get("api_key", "")
    if not voyage_key:
        print("ERROR: No Voyage API key in config.json")
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
        print(f"\nEmbedding done: {count} chunks in {elapsed:.1f}s")
        from pipeline.vector_store import get_stats
        print(f"LanceDB total vectors: {get_stats()['count']}")
    else:
        print("No new chunks to embed")

    return count


def main():
    parser = argparse.ArgumentParser(description="Expanded pipeline: crawl -> chunk -> embed")
    parser.add_argument("--step", choices=["crawl", "chunk", "embed"], default=None)
    parser.add_argument("--force", action="store_true", help="Re-process already parsed pages")
    args = parser.parse_args()

    from core.config import load_config
    from pipeline.db import init_db

    cfg = load_config()
    init_db()

    steps = [args.step] if args.step else ["crawl", "chunk", "embed"]

    print("=" * 50)
    print("Grimoire Expanded Pipeline")
    print("=" * 50)

    if "crawl" in steps:
        print("\n> Step 1/3: Crawling new categories")
        _step_crawl(cfg)

    if "chunk" in steps:
        print("\n> Step 2/3: Chunking")
        _step_chunk(force=args.force)

    if "embed" in steps:
        print("\n> Step 3/3: Embedding (voyage-4)")
        _step_embed(cfg)

    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
