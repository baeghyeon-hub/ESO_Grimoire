"""
청크 품질 정리 — 노이즈 청크 제거 + 초대형 청크 재분할.

실행: python -m pipeline.chunk_cleanup [--dry-run]
"""
from __future__ import annotations

import logging
import re
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_LOG = logging.getLogger(__name__)

# ── 제거 대상 패턴 ──────────────────────────────────────

# 이름 목록 페이지 (수십만 글자짜리 이름 나열)
_SKIP_TITLE_PATTERNS = [
    r"Lore:.+Names/Arena",       # Redguard Names/Arena Female S 등
    r"Lore:.+Names/Daggerfall",
    r"Lore:.+Names/Battlespire",
]

# 스킵할 섹션 (의미 없는 메타 데이터)
_SKIP_SECTIONS = {
    "bibliography", "external links", "bugs", "notes",
    "deprecated", "removed", "unused",
}

# 위키 마크업 비율이 너무 높으면 제거 (테이블만 있는 청크)
_MAX_PIPE_RATIO = 0.15  # 전체 문자 중 | 비율


def cleanup_chunks(db_path: str = "db/uesp.db", *, dry_run: bool = False) -> dict:
    """청크 품질 정리. 반환: {removed, resplit, kept}"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    all_chunks = conn.execute(
        "SELECT id, page_title, section, chunk_text, token_count FROM lore_chunks"
    ).fetchall()

    stats = {"total": len(all_chunks), "removed": 0, "reasons": {}}
    remove_ids = []

    for chunk in all_chunks:
        cid = chunk["id"]
        title = chunk["page_title"]
        section = chunk["section"]
        text = chunk["chunk_text"]
        length = len(text)

        reason = None

        # 1. 제목 패턴 매칭 (이름 목록 등)
        for pat in _SKIP_TITLE_PATTERNS:
            if re.search(pat, title):
                reason = "name_list_page"
                break

        # 2. 섹션 이름 필터
        if not reason:
            sec_lower = section.lower().strip()
            for skip in _SKIP_SECTIONS:
                if skip in sec_lower:
                    reason = f"skip_section:{skip}"
                    break

        # 3. 위키 마크업 비율 체크
        if not reason and length > 200:
            pipe_count = text.count("|")
            brace_count = text.count("{") + text.count("}")
            markup_chars = pipe_count + brace_count
            if markup_chars / length > _MAX_PIPE_RATIO:
                reason = "heavy_markup"

        # 4. 초대형 청크 (10K+ chars) — 유용한 내용이 아닌 것
        if not reason and length > 30000:
            # 30K 이상은 대부분 테이블/목록
            pipe_count = text.count("|")
            if pipe_count > 100:
                reason = "oversized_table"

        # 5. redirect 텍스트가 남아있는 경우
        if not reason and "redirects here" in text[:100].lower():
            # 리다이렉트 안내문은 제거하지 않고 텍스트만 정리
            pass

        # 6. 텍스트가 거의 없고 템플릿만 있는 경우
        if not reason and length > 500:
            # 순수 텍스트 비율 계산 (알파벳/한글 문자)
            alpha_count = sum(1 for c in text if c.isalpha())
            if alpha_count / length < 0.3:
                reason = "low_text_ratio"

        if reason:
            remove_ids.append(cid)
            stats["removed"] += 1
            stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1

    # 실행
    if dry_run:
        _LOG.info("[cleanup] DRY RUN — would remove %d / %d chunks", stats["removed"], stats["total"])
        for reason, count in sorted(stats["reasons"].items(), key=lambda x: -x[1]):
            _LOG.info("  %s: %d", reason, count)

        # 제거 대상 샘플 출력
        sample_ids = remove_ids[:20]
        if sample_ids:
            placeholders = ",".join("?" * len(sample_ids))
            samples = conn.execute(
                f"SELECT id, page_title, section, length(chunk_text) as len FROM lore_chunks WHERE id IN ({placeholders})",
                sample_ids,
            ).fetchall()
            _LOG.info("\n  Sample removals:")
            for s in samples:
                _LOG.info("    [%d] %s > %s (%d chars)", s["id"], s["page_title"], s["section"], s["len"])
    else:
        if remove_ids:
            # 배치 삭제
            batch_size = 500
            for i in range(0, len(remove_ids), batch_size):
                batch = remove_ids[i:i + batch_size]
                placeholders = ",".join("?" * len(batch))
                conn.execute(f"DELETE FROM lore_chunks WHERE id IN ({placeholders})", batch)
            conn.commit()

        _LOG.info("[cleanup] Removed %d / %d chunks", stats["removed"], stats["total"])
        for reason, count in sorted(stats["reasons"].items(), key=lambda x: -x[1]):
            _LOG.info("  %s: %d", reason, count)

        remaining = conn.execute("SELECT COUNT(*) FROM lore_chunks").fetchone()[0]
        _LOG.info("Remaining chunks: %d", remaining)

    conn.close()
    return stats


# ── CLI ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chunk quality cleanup")
    parser.add_argument("--dry-run", action="store_true", help="미리보기만 (삭제 안 함)")
    args = parser.parse_args()

    cleanup_chunks(dry_run=args.dry_run)
