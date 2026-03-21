"""
Indexer — 크롤링된 페이지를 파싱하여 구조화된 데이터로 DB에 저장.

crawl → parse → index 파이프라인의 마지막 단계.
도메인별 파서를 사용하여 pages → 도메인 테이블로 인덱싱한다.
"""
from __future__ import annotations

import logging
from datetime import datetime

from pipeline.db import get_db, init_db
from pipeline.parsers import PARSERS
from pipeline.parsers.sets import parse_set

_LOG = logging.getLogger(__name__)

# 도메인 → pages.category 매핑 (같은 파서를 쓰는 카테고리 통합)
_DOMAIN_CATEGORIES = {
    "sets": ["sets"],
    "skills": ["skills"],
    "dungeons": ["dungeons", "trials", "arenas"],
    "zones": ["zones"],
    "companions": ["companions"],
    "alchemy": ["alchemy"],
    "quests": ["quests"],
    "npcs": ["npcs"],
}

# 도메인별 DB 저장 함수
def _save_set(conn, parsed, title):
    existing = conn.execute(
        "SELECT id FROM sets WHERE name = ? COLLATE NOCASE", (parsed.name,)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM set_bonuses WHERE set_id = ?", (existing["id"],))
        conn.execute("DELETE FROM sets WHERE id = ?", (existing["id"],))

    cursor = conn.execute(
        """INSERT INTO sets (name, page_title, set_type, armor_type, location, dlc, craftable, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.set_type, parsed.armor_type,
         parsed.location, parsed.dlc, 1 if parsed.craftable else 0, parsed.description),
    )
    set_id = cursor.lastrowid
    for bonus in parsed.bonuses:
        conn.execute(
            "INSERT INTO set_bonuses (set_id, piece_count, bonus_text) VALUES (?, ?, ?)",
            (set_id, bonus.piece_count, bonus.bonus_text),
        )


def _save_skill(conn, parsed, title):
    conn.execute("DELETE FROM skills WHERE name = ? COLLATE NOCASE", (parsed.name,))
    conn.execute(
        """INSERT INTO skills (name, page_title, skill_line, cost, attrib, cast_time,
           target, duration, range_info, description, morph1_name, morph1_desc, morph2_name, morph2_desc)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.skill_line, parsed.cost, parsed.attrib,
         parsed.cast_time, parsed.target, parsed.duration, parsed.range,
         parsed.description, parsed.morph1_name, parsed.morph1_desc,
         parsed.morph2_name, parsed.morph2_desc),
    )


def _save_dungeon(conn, parsed, title):
    existing = conn.execute(
        "SELECT id FROM dungeons WHERE name = ? COLLATE NOCASE", (parsed.name,)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM dungeon_bosses WHERE dungeon_id = ?", (existing["id"],))
        conn.execute("DELETE FROM dungeon_sets WHERE dungeon_id = ?", (existing["id"],))
        conn.execute("DELETE FROM dungeons WHERE id = ?", (existing["id"],))

    cursor = conn.execute(
        """INSERT INTO dungeons (name, page_title, dungeon_type, zone, dlc, group_size, min_level, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.dungeon_type, parsed.zone, parsed.dlc,
         parsed.group_size, parsed.min_level, parsed.description),
    )
    dungeon_id = cursor.lastrowid
    for boss in parsed.bosses:
        conn.execute(
            "INSERT INTO dungeon_bosses (dungeon_id, boss_name, boss_type, strategy) VALUES (?, ?, ?, ?)",
            (dungeon_id, boss.boss_name, boss.boss_type, boss.strategy),
        )
    for set_name in parsed.set_names:
        conn.execute(
            "INSERT INTO dungeon_sets (dungeon_id, set_name) VALUES (?, ?)",
            (dungeon_id, set_name),
        )


def _save_zone(conn, parsed, title):
    conn.execute("DELETE FROM zones WHERE name = ? COLLATE NOCASE", (parsed.name,))
    conn.execute(
        """INSERT INTO zones (name, page_title, zone_type, dlc, alliance, wayshrines,
           delves, public_dungeons, group_dungeons, world_bosses, skyshards, set_stations,
           quests, hub, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.zone_type, parsed.dlc, parsed.alliance,
         parsed.wayshrines, parsed.delves, parsed.public_dungeons, parsed.group_dungeons,
         parsed.world_bosses, parsed.skyshards, parsed.set_stations,
         parsed.quests, parsed.hub, parsed.description),
    )


def _save_companion(conn, parsed, title):
    conn.execute("DELETE FROM companions WHERE name = ? COLLATE NOCASE", (parsed.name,))
    conn.execute(
        """INSERT INTO companions (name, page_title, race, gender, location, dlc, perk, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.race, parsed.gender, parsed.location,
         parsed.dlc, parsed.perk, parsed.description),
    )


def _save_reagent(conn, parsed, title):
    conn.execute("DELETE FROM alchemy_reagents WHERE name = ? COLLATE NOCASE", (parsed.name,))
    conn.execute(
        """INSERT INTO alchemy_reagents (name, page_title, effect1, effect2, effect3, effect4)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.effect1, parsed.effect2, parsed.effect3, parsed.effect4),
    )


def _save_quest(conn, parsed, title):
    conn.execute("DELETE FROM quests WHERE page_title = ?", (title,))
    conn.execute(
        """INSERT INTO quests (name, page_title, quest_type, zone, giver, location,
           dlc, skill_point, description, quest_id, prev_quest, next_quest)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.quest_type, parsed.zone, parsed.giver,
         parsed.location, parsed.dlc, parsed.skill_point, parsed.description,
         parsed.quest_id, parsed.prev_quest, parsed.next_quest),
    )


def _save_npc(conn, parsed, title):
    conn.execute("DELETE FROM npcs WHERE page_title = ?", (title,))
    conn.execute(
        """INSERT INTO npcs (name, page_title, race, gender, location, zone, reaction, services, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (parsed.name, title, parsed.race, parsed.gender, parsed.location,
         parsed.zone, parsed.reaction, parsed.services, parsed.description),
    )


_DOMAIN_SAVERS = {
    "sets": _save_set,
    "skills": _save_skill,
    "dungeons": _save_dungeon,
    "zones": _save_zone,
    "companions": _save_companion,
    "alchemy": _save_reagent,
    "quests": _save_quest,
    "npcs": _save_npc,
}


def index_domain(domain: str, *, force: bool = False, progress_fn=None) -> int:
    """도메인의 페이지를 파싱하여 구조화된 테이블에 저장.

    Args:
        domain: 도메인 이름 (sets, skills, dungeons, zones, ...)
        force: True면 이미 파싱된 페이지도 다시 처리
        progress_fn: 진행 콜백 fn(current, total, title)

    Returns:
        저장된 레코드 수
    """
    init_db()

    categories = _DOMAIN_CATEGORIES.get(domain, [domain])
    parser_name = domain
    # dungeons 도메인은 dungeons/trials/arenas 파서를 공유
    if domain == "dungeons":
        parser_name = "dungeons"

    parser_fn = PARSERS.get(parser_name)
    save_fn = _DOMAIN_SAVERS.get(domain)
    if not parser_fn or not save_fn:
        _LOG.error("[indexer] unknown domain: %s", domain)
        return 0

    # 카테고리 목록에서 페이지 조회
    placeholders = ",".join("?" * len(categories))
    with get_db() as conn:
        if force:
            rows = conn.execute(
                f"SELECT id, title, wikitext FROM pages WHERE category IN ({placeholders})",
                categories,
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT id, title, wikitext FROM pages WHERE category IN ({placeholders}) AND parsed_at IS NULL",
                categories,
            ).fetchall()

    total = len(rows)
    _LOG.info("[indexer] %s: %d pages to parse", domain, total)
    saved = 0

    for i, row in enumerate(rows):
        page_id = row["id"]
        title = row["title"]
        wikitext = row["wikitext"]

        if progress_fn:
            progress_fn(i + 1, total, title)

        parsed = parser_fn(title, wikitext)
        if not parsed:
            _LOG.debug("[indexer] parse failed: %s", title)
            with get_db() as conn:
                conn.execute(
                    "UPDATE pages SET parsed_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), page_id),
                )
            continue

        with get_db() as conn:
            save_fn(conn, parsed, title)
            conn.execute(
                "UPDATE pages SET parsed_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), page_id),
            )
        saved += 1

    _LOG.info("[indexer] %s: %d records indexed", domain, saved)
    return saved


# ── 하위호환 ────────────────────────────────────────────

def index_sets(*, force: bool = False, progress_fn=None) -> int:
    """기존 호환용."""
    return index_domain("sets", force=force, progress_fn=progress_fn)


def reindex_all() -> int:
    """모든 도메인 재인덱싱."""
    total = 0
    for domain in _DOMAIN_CATEGORIES:
        total += index_domain(domain, force=True)
    return total


# ── CLI ──────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    all_domains = list(_DOMAIN_CATEGORIES.keys()) + ["all"]
    parser = argparse.ArgumentParser(description="UESP Domain Indexer")
    parser.add_argument("domain", choices=all_domains, help="인덱싱 대상 도메인")
    parser.add_argument("--force", action="store_true", help="이미 파싱된 페이지도 다시 처리")
    args = parser.parse_args()

    def progress(cur, total, title):
        try:
            print(f"  [{cur}/{total}] {title}")
        except UnicodeEncodeError:
            print(f"  [{cur}/{total}] {title.encode('ascii', 'replace').decode()}")

    if args.domain == "all":
        domains = list(_DOMAIN_CATEGORIES.keys())
    else:
        domains = [args.domain]

    for domain in domains:
        print(f"\n=== Indexing: {domain} ===")
        saved = index_domain(domain, force=args.force, progress_fn=progress)
        print(f"  -> {saved} records indexed")


if __name__ == "__main__":
    main()
