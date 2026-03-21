"""
SQLite 데이터베이스 — UESP 크롤링 데이터 저장소.

테이블:
  pages       — 원본 wikitext 페이지 (크롤링 결과)
  sets        — 구조화된 세트 데이터
  set_bonuses — 세트별 피스 보너스
  pages_fts   — FTS5 전문 검색 인덱스
"""
from __future__ import annotations

import os
import sqlite3
import sys
import threading
from contextlib import contextmanager

_DB_NAME = "uesp.db"


def _db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "db", _DB_NAME)


_SCHEMA = """
-- 원본 페이지 데이터 (크롤링)
CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL UNIQUE,
    namespace   INTEGER NOT NULL DEFAULT 144,
    wikitext    TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT '',
    crawled_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    parsed_at   TEXT
);

-- 구조화된 세트 데이터
CREATE TABLE IF NOT EXISTS sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    page_title  TEXT    NOT NULL,
    set_type    TEXT    NOT NULL DEFAULT '',
    armor_type  TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    dlc         TEXT    NOT NULL DEFAULT '',
    craftable   INTEGER NOT NULL DEFAULT 0,
    description TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- 세트 피스 보너스
CREATE TABLE IF NOT EXISTS set_bonuses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id      INTEGER NOT NULL,
    piece_count INTEGER NOT NULL,
    bonus_text  TEXT    NOT NULL,
    FOREIGN KEY (set_id) REFERENCES sets(id) ON DELETE CASCADE
);

-- FTS5 전문 검색 (페이지 텍스트)
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title,
    wikitext,
    content='pages',
    content_rowid='id',
    tokenize='unicode61'
);

-- FTS 자동 동기화 트리거
CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, title, wikitext)
    VALUES (new.id, new.title, new.wikitext);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, wikitext)
    VALUES ('delete', old.id, old.title, old.wikitext);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, wikitext)
    VALUES ('delete', old.id, old.title, old.wikitext);
    INSERT INTO pages_fts(rowid, title, wikitext)
    VALUES (new.id, new.title, new.wikitext);
END;

-- 구조화된 스킬 데이터
CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    page_title  TEXT    NOT NULL,
    skill_line  TEXT    NOT NULL DEFAULT '',
    cost        TEXT    NOT NULL DEFAULT '',
    attrib      TEXT    NOT NULL DEFAULT '',
    cast_time   TEXT    NOT NULL DEFAULT '',
    target      TEXT    NOT NULL DEFAULT '',
    duration    TEXT    NOT NULL DEFAULT '',
    range_info  TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    morph1_name TEXT    NOT NULL DEFAULT '',
    morph1_desc TEXT    NOT NULL DEFAULT '',
    morph2_name TEXT    NOT NULL DEFAULT '',
    morph2_desc TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- 던전/트라이얼/아레나
CREATE TABLE IF NOT EXISTS dungeons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL UNIQUE,
    page_title   TEXT    NOT NULL,
    dungeon_type TEXT    NOT NULL DEFAULT '',
    zone         TEXT    NOT NULL DEFAULT '',
    dlc          TEXT    NOT NULL DEFAULT '',
    group_size   INTEGER NOT NULL DEFAULT 0,
    min_level    INTEGER NOT NULL DEFAULT 0,
    description  TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

CREATE TABLE IF NOT EXISTS dungeon_bosses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dungeon_id  INTEGER NOT NULL,
    boss_name   TEXT    NOT NULL,
    boss_type   TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (dungeon_id) REFERENCES dungeons(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dungeon_sets (
    dungeon_id  INTEGER NOT NULL,
    set_name    TEXT    NOT NULL,
    FOREIGN KEY (dungeon_id) REFERENCES dungeons(id) ON DELETE CASCADE
);

-- 존/지역
CREATE TABLE IF NOT EXISTS zones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    page_title      TEXT    NOT NULL,
    zone_type       TEXT    NOT NULL DEFAULT '',
    dlc             TEXT    NOT NULL DEFAULT '',
    alliance        TEXT    NOT NULL DEFAULT '',
    wayshrines      INTEGER NOT NULL DEFAULT 0,
    delves          INTEGER NOT NULL DEFAULT 0,
    public_dungeons INTEGER NOT NULL DEFAULT 0,
    group_dungeons  INTEGER NOT NULL DEFAULT 0,
    world_bosses    INTEGER NOT NULL DEFAULT 0,
    skyshards       INTEGER NOT NULL DEFAULT 0,
    set_stations    INTEGER NOT NULL DEFAULT 0,
    quests          INTEGER NOT NULL DEFAULT 0,
    hub             TEXT    NOT NULL DEFAULT '',
    description     TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- 컴패니언
CREATE TABLE IF NOT EXISTS companions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    page_title  TEXT    NOT NULL,
    race        TEXT    NOT NULL DEFAULT '',
    gender      TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    dlc         TEXT    NOT NULL DEFAULT '',
    perk        TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- 연금술 재료
CREATE TABLE IF NOT EXISTS alchemy_reagents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    page_title  TEXT    NOT NULL,
    effect1     TEXT    NOT NULL DEFAULT '',
    effect2     TEXT    NOT NULL DEFAULT '',
    effect3     TEXT    NOT NULL DEFAULT '',
    effect4     TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- 퀘스트
CREATE TABLE IF NOT EXISTS quests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    page_title  TEXT    NOT NULL UNIQUE,
    quest_type  TEXT    NOT NULL DEFAULT '',
    zone        TEXT    NOT NULL DEFAULT '',
    giver       TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    dlc         TEXT    NOT NULL DEFAULT '',
    skill_point INTEGER NOT NULL DEFAULT 0,
    description TEXT    NOT NULL DEFAULT '',
    quest_id    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- NPC
CREATE TABLE IF NOT EXISTS npcs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    page_title  TEXT    NOT NULL UNIQUE,
    race        TEXT    NOT NULL DEFAULT '',
    gender      TEXT    NOT NULL DEFAULT '',
    location    TEXT    NOT NULL DEFAULT '',
    zone        TEXT    NOT NULL DEFAULT '',
    reaction    TEXT    NOT NULL DEFAULT '',
    services    TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (page_title) REFERENCES pages(title)
);

-- ── 관계 테이블 (Phase 1) ─────────────────────────────

-- 퀘스트 ↔ NPC 관계
CREATE TABLE IF NOT EXISTS quest_npcs (
    quest_id    INTEGER NOT NULL,
    npc_name    TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'giver',
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

-- 존 ↔ 던전 관계
CREATE TABLE IF NOT EXISTS zone_dungeons (
    zone_id     INTEGER NOT NULL,
    dungeon_id  INTEGER NOT NULL,
    FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
    FOREIGN KEY (dungeon_id) REFERENCES dungeons(id) ON DELETE CASCADE,
    UNIQUE(zone_id, dungeon_id)
);

-- 연금술 효과 (정규화)
CREATE TABLE IF NOT EXISTS alchemy_effects (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE
);

-- 재료 ↔ 효과 관계
CREATE TABLE IF NOT EXISTS reagent_effects (
    reagent_id  INTEGER NOT NULL,
    effect_id   INTEGER NOT NULL,
    slot        INTEGER NOT NULL,
    FOREIGN KEY (reagent_id) REFERENCES alchemy_reagents(id) ON DELETE CASCADE,
    FOREIGN KEY (effect_id) REFERENCES alchemy_effects(id) ON DELETE CASCADE,
    UNIQUE(reagent_id, effect_id)
);

-- 사전 계산된 연금술 조합
CREATE TABLE IF NOT EXISTS alchemy_combinations (
    reagent1_id   INTEGER NOT NULL,
    reagent2_id   INTEGER NOT NULL,
    shared_effect TEXT    NOT NULL,
    FOREIGN KEY (reagent1_id) REFERENCES alchemy_reagents(id),
    FOREIGN KEY (reagent2_id) REFERENCES alchemy_reagents(id),
    UNIQUE(reagent1_id, reagent2_id, shared_effect)
);

-- ── Lore 청크 (Phase 2 — 벡터 검색용) ───────────────────

CREATE TABLE IF NOT EXISTS lore_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_title  TEXT    NOT NULL,
    section     TEXT    NOT NULL DEFAULT '',
    chunk_text  TEXT    NOT NULL,
    chunk_hash  TEXT    NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    embedded_at TEXT,
    FOREIGN KEY (page_title) REFERENCES pages(title) ON DELETE CASCADE
);

-- Lore FTS5 (BM25 하이브리드 검색용)
CREATE VIRTUAL TABLE IF NOT EXISTS lore_chunks_fts USING fts5(
    page_title, section, chunk_text,
    content='lore_chunks', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS lore_chunks_ai AFTER INSERT ON lore_chunks BEGIN
    INSERT INTO lore_chunks_fts(rowid, page_title, section, chunk_text)
    VALUES (new.id, new.page_title, new.section, new.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS lore_chunks_ad AFTER DELETE ON lore_chunks BEGIN
    INSERT INTO lore_chunks_fts(lore_chunks_fts, rowid, page_title, section, chunk_text)
    VALUES ('delete', old.id, old.page_title, old.section, old.chunk_text);
END;

CREATE TRIGGER IF NOT EXISTS lore_chunks_au AFTER UPDATE ON lore_chunks BEGIN
    INSERT INTO lore_chunks_fts(lore_chunks_fts, rowid, page_title, section, chunk_text)
    VALUES ('delete', old.id, old.page_title, old.section, old.chunk_text);
    INSERT INTO lore_chunks_fts(rowid, page_title, section, chunk_text)
    VALUES (new.id, new.page_title, new.section, new.chunk_text);
END;

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_lore_chunks_page ON lore_chunks(page_title);
CREATE INDEX IF NOT EXISTS idx_lore_chunks_hash ON lore_chunks(chunk_hash);
CREATE INDEX IF NOT EXISTS idx_pages_category ON pages(category);
CREATE INDEX IF NOT EXISTS idx_sets_type ON sets(set_type);
CREATE INDEX IF NOT EXISTS idx_sets_location ON sets(location);
CREATE INDEX IF NOT EXISTS idx_set_bonuses_set_id ON set_bonuses(set_id);
CREATE INDEX IF NOT EXISTS idx_skills_line ON skills(skill_line);
CREATE INDEX IF NOT EXISTS idx_skills_attrib ON skills(attrib);
CREATE INDEX IF NOT EXISTS idx_dungeons_type ON dungeons(dungeon_type);
CREATE INDEX IF NOT EXISTS idx_dungeons_zone ON dungeons(zone);
CREATE INDEX IF NOT EXISTS idx_zones_dlc ON zones(dlc);
CREATE INDEX IF NOT EXISTS idx_quests_zone ON quests(zone);
CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(quest_type);
CREATE INDEX IF NOT EXISTS idx_npcs_zone ON npcs(zone);
CREATE INDEX IF NOT EXISTS idx_npcs_race ON npcs(race);
CREATE INDEX IF NOT EXISTS idx_quest_npcs_npc ON quest_npcs(npc_name);
CREATE INDEX IF NOT EXISTS idx_quest_npcs_quest ON quest_npcs(quest_id);
CREATE INDEX IF NOT EXISTS idx_alchemy_combo_effect ON alchemy_combinations(shared_effect);
CREATE INDEX IF NOT EXISTS idx_reagent_effects_reagent ON reagent_effects(reagent_id);
CREATE INDEX IF NOT EXISTS idx_reagent_effects_effect ON reagent_effects(effect_id);
"""

_MIGRATIONS = [
    ("quests", "prev_quest", "ALTER TABLE quests ADD COLUMN prev_quest TEXT NOT NULL DEFAULT ''"),
    ("quests", "next_quest", "ALTER TABLE quests ADD COLUMN next_quest TEXT NOT NULL DEFAULT ''"),
    ("dungeon_bosses", "strategy", "ALTER TABLE dungeon_bosses ADD COLUMN strategy TEXT NOT NULL DEFAULT ''"),
]

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """스레드별 커넥션 반환 (재사용)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        path = _db_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """DB 초기화 — 테이블/인덱스 생성 + 마이그레이션."""
    conn = _get_conn()
    conn.executescript(_SCHEMA)
    # ALTER TABLE 마이그레이션 (컬럼이 없으면 추가)
    for table, column, sql in _MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            conn.execute(sql)
    conn.commit()


@contextmanager
def get_db():
    """DB 커넥션 컨텍스트 매니저."""
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── 쿼리 헬퍼 ──────────────────────────────────────────

def search_fts(query: str, limit: int = 10) -> list[dict]:
    """FTS5 전문 검색."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT p.title, snippet(pages_fts, 1, '>>>', '<<<', '...', 40) AS snippet,
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


def _sanitize_fts_query(query: str) -> str:
    """FTS5 쿼리에서 특수문자 제거, 단어를 OR로 연결."""
    import re
    # 알파벳, 숫자, 한글, 일본어, 중국어만 남김
    words = re.findall(r"[\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+", query)
    if not words:
        return ""
    # 각 단어를 큰따옴표로 감싸고 OR 연결
    return " OR ".join(f'"{w}"' for w in words)


def search_lore_fts(query: str, limit: int = 10) -> list[dict]:
    """FTS5 전문 검색 — lore_chunks."""
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return []
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT lc.id, lc.page_title, lc.section,
               snippet(lore_chunks_fts, 2, '>>>', '<<<', '...', 60) AS snippet,
               rank
        FROM lore_chunks_fts
        JOIN lore_chunks lc ON lc.id = lore_chunks_fts.rowid
        WHERE lore_chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (sanitized, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_set_by_name(name: str) -> dict | None:
    """세트 이름으로 세트 + 보너스 조회."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM sets WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if not row:
        return None

    set_data = dict(row)
    bonuses = conn.execute(
        "SELECT piece_count, bonus_text FROM set_bonuses WHERE set_id = ? ORDER BY piece_count",
        (set_data["id"],),
    ).fetchall()
    set_data["bonuses"] = [dict(b) for b in bonuses]
    return set_data


def search_sets(query: str, limit: int = 10) -> list[dict]:
    """세트 이름 LIKE 검색."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM sets WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT ?",
        (f"%{query}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def filter_sets(
    *,
    set_type: str = "",
    armor_type: str = "",
    location: str = "",
    craftable: bool | None = None,
    limit: int = 50,
) -> list[dict]:
    """조건별 세트 필터링."""
    conn = _get_conn()
    conditions = []
    params = []

    if set_type:
        conditions.append("set_type LIKE ? COLLATE NOCASE")
        params.append(f"%{set_type}%")
    if armor_type:
        conditions.append("armor_type LIKE ? COLLATE NOCASE")
        params.append(f"%{armor_type}%")
    if location:
        conditions.append("location LIKE ? COLLATE NOCASE")
        params.append(f"%{location}%")
    if craftable is not None:
        conditions.append("craftable = ?")
        params.append(1 if craftable else 0)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM sets WHERE {where} ORDER BY name LIMIT ?", params
    ).fetchall()
    return [dict(r) for r in rows]


def search_by_stat(stat_type: str, limit: int = 20) -> list[dict]:
    """특정 스탯 보너스를 가진 세트 검색."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT s.name, s.set_type, s.armor_type, s.location,
               b.piece_count, b.bonus_text, b.stat_type, b.stat_value
        FROM sets s
        JOIN set_bonuses b ON s.id = b.set_id
        WHERE b.stat_type LIKE ? COLLATE NOCASE
        ORDER BY s.name
        LIMIT ?
        """,
        (f"%{stat_type}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def compare_sets(names: list[str]) -> list[dict]:
    """여러 세트를 비교용으로 조회."""
    conn = _get_conn()
    results = []
    for name in names:
        data = get_set_by_name(name)
        if data:
            results.append(data)
    return results


def get_db_stats() -> dict:
    """DB 통계."""
    conn = _get_conn()
    pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    sets = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
    bonuses = conn.execute("SELECT COUNT(*) FROM set_bonuses").fetchone()[0]
    return {"pages": pages, "sets": sets, "bonuses": bonuses}
