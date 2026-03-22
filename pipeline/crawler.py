"""
UESP Crawler — ESO 위키 페이지를 크롤링하여 DB에 저장.

MediaWiki API를 직접 호출하여 ESO namespace(144) 페이지를 수집한다.
카테고리별 크롤링을 지원하며, 증분 업데이트가 가능하다.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

import requests

from pipeline.db import get_db, init_db

_LOG = logging.getLogger(__name__)

_UESP_API = "https://en.uesp.net/w/api.php"
_USER_AGENT = "ESO-UESP-RAG/2.0 (Crawler)"
_ESO_NS = 144
_LORE_NS = 130

# 크롤링 대상 카테고리
CATEGORIES = {
    "sets": "Online-Sets",
    "skills": "Online-Skills",
    "dungeons": "Online-Places-Group Dungeons",
    "trials": "Online-Places-Trials",
    "arenas": "Online-Places-Arenas",
    "zones": "Online-Places-Zones",
    "companions": "Online-Companions",
    "alchemy": "Online-Alchemy",
    "npcs": "Online-NPCs",
    "achievements": "Online-Achievements",
    "antiquities": "Online-Antiquities",
    "cp_passive": "Online-Champion-Passive",
    "cp_slotted": "Online-Champion-Slotted",
    "furnishings": "Online-Furnishings",
    "recipes": "Online-Recipes",
    "food": "Online-Food",
    "delves": "Online-Places-Delves",
    "public_dungeons": "Online-Places-Public Dungeons",
    "factions": "Online-Factions",
    "crown_store": "Online-Crown Store",
    "mounts": "Online-Mounts",
    "mementos": "Online-Mementos",
    "skill_styles": "Online-Skill Styles",
    "classes": "Online-Classes",
    "items": "Online-Items",
    "combat": "Online-Combat",
    "armor": "Online-Armor",
    "races": "Online-Races",
    "events": "Online-Events",
    "activities": "Online-Activities",
    "alliance_war": "Online-Alliance War",
}

# 퀘스트 서브카테고리 (재귀 크롤링 대상)
QUEST_PARENT_CATEGORY = "Online-Quests"

# Lore 카테고리
LORE_CATEGORIES = {
    "lore-people": "Lore-People",
    "lore-gods": "Lore-Gods",
    "lore-races": "Lore-Races",
    "lore-places": "Lore-Places",
    "lore-books": "Lore-Books",
    "lore-factions": "Lore-Factions",
    "lore-creatures": "Lore-Creatures",
    "lore-flora": "Lore-Flora",
    "lore-history": "Lore-History",
    "lore-magic": "Lore-Magic",
    "lore-appendices": "Lore-Appendices",
    "lore-disease": "Lore-Disease",
    "lore-calendar": "Lore-Calendar",
    "lore-names": "Lore-Names",
    "lore-daedra": "Lore-Daedra",
    "lore-archive": "Lore-Loremaster's Archive",
    "lore-undead": "Lore-Undead",
    "lore-linguistics": "Lore-Linguistics",
    "lore-spells": "Lore-Spells",
    "lore-empires": "Lore-Empires",
}


class UESPCrawler:
    """UESP MediaWiki API 크롤러."""

    def __init__(self, delay: float = 0.5):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT
        self._delay = delay  # 요청 간 대기 (초)

    def crawl_category(
        self,
        category: str,
        *,
        limit: int = 0,
        skip_existing: bool = True,
        progress_fn=None,
    ) -> int:
        """카테고리의 페이지를 크롤링하여 DB에 저장.

        Args:
            category: CATEGORIES 키 또는 직접 카테고리명 (예: "Online-Sets")
            limit: 최대 페이지 수 (0=무제한)
            skip_existing: True면 DB에 이미 있는 페이지 건너뜀
            progress_fn: 진행 콜백 fn(current, total, title)

        Returns:
            저장된 페이지 수
        """
        init_db()
        cat_name = CATEGORIES.get(category, category)

        # 1) 카테고리 멤버 목록 수집
        titles = self._list_category_members(cat_name, limit=limit)
        _LOG.info("[crawler] category '%s': %d pages found", cat_name, len(titles))

        if not titles:
            return 0

        # 2) 기존 페이지 필터링
        if skip_existing:
            with get_db() as conn:
                existing = {
                    row[0]
                    for row in conn.execute(
                        "SELECT title FROM pages WHERE category = ?", (category,)
                    ).fetchall()
                }
            titles = [t for t in titles if t not in existing]
            _LOG.info("[crawler] %d new pages to crawl (skipped %d existing)",
                      len(titles), len(existing))

        # 3) 각 페이지 wikitext 수집
        saved = 0
        total = len(titles)
        for i, title in enumerate(titles):
            if progress_fn:
                progress_fn(i + 1, total, title)

            wikitext = self._fetch_wikitext(title)
            if not wikitext:
                _LOG.warning("[crawler] empty wikitext: %s", title)
                continue

            # 리다이렉트 페이지 스킵
            if wikitext.strip().upper().startswith("#REDIRECT"):
                _LOG.debug("[crawler] redirect skipped: %s", title)
                continue

            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO pages (title, namespace, wikitext, category, crawled_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(title) DO UPDATE SET
                        wikitext = excluded.wikitext,
                        crawled_at = excluded.crawled_at
                    """,
                    (title, _ESO_NS, wikitext, category, datetime.utcnow().isoformat()),
                )
            saved += 1

            if self._delay > 0:
                time.sleep(self._delay)

        _LOG.info("[crawler] category '%s': %d pages saved", cat_name, saved)
        return saved

    def crawl_page(self, title: str, category: str = "") -> bool:
        """단일 페이지 크롤링."""
        init_db()
        wikitext = self._fetch_wikitext(title)
        if not wikitext:
            return False

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO pages (title, namespace, wikitext, category, crawled_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(title) DO UPDATE SET
                    wikitext = excluded.wikitext,
                    crawled_at = excluded.crawled_at
                """,
                (title, _ESO_NS, wikitext, category, datetime.utcnow().isoformat()),
            )
        return True

    def crawl_quests(
        self,
        *,
        limit: int = 0,
        skip_existing: bool = True,
        progress_fn=None,
    ) -> int:
        """퀘스트 서브카테고리를 재귀적으로 크롤링.

        Online-Quests 아래 서브카테고리(Online-Quests-Main Quest 등)를
        자동 탐색하여 모든 퀘스트 페이지를 수집한다.
        """
        init_db()
        subcats = self._list_subcategories(QUEST_PARENT_CATEGORY)
        _LOG.info("[crawler] found %d quest subcategories", len(subcats))

        total_saved = 0
        for subcat in subcats:
            _LOG.info("[crawler] crawling quest subcat: %s", subcat)
            saved = self.crawl_category(
                subcat,  # 직접 카테고리명 전달 (CATEGORIES 매핑 바이패스)
                limit=limit,
                skip_existing=skip_existing,
                progress_fn=progress_fn,
            )
            # 저장된 페이지의 category를 'quests'로 통일
            if saved > 0:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE pages SET category = 'quests' WHERE category = ?",
                        (subcat,),
                    )
            total_saved += saved

        _LOG.info("[crawler] quests total: %d pages saved", total_saved)
        return total_saved

    def _list_subcategories(self, parent_category: str) -> list[str]:
        """카테고리의 서브카테고리 목록 반환."""
        subcats = []
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{parent_category}",
            "cmtype": "subcat",
            "cmlimit": "500",
            "format": "json",
        }
        while True:
            data = self._api_get(params)
            if not data:
                break
            members = data.get("query", {}).get("categorymembers", [])
            for m in members:
                # "Category:Online-Quests-Main Quest" → "Online-Quests-Main Quest"
                name = m["title"].replace("Category:", "")
                subcats.append(name)
            cont = data.get("continue")
            if not cont:
                break
            params.update(cont)
            time.sleep(self._delay)
        return subcats

    # ── MediaWiki API ─────────────────────────────────

    # 인덱스/목록 페이지 — 크롤링에서 제외
    _SKIP_TITLES = {
        "Online:Craftable Sets", "Online:Monster Helm Sets", "Online:Arena Sets",
        "Online:Dungeon Sets", "Online:Jewelry Sets", "Online:Overland Sets",
        "Online:Trial Sets", "Online:Weapon Sets", "Online:PvP Sets",
        "Online:Sets", "Online:Mythic Items", "Online:Item Sets",
        "Online:Skills", "Online:Champion Points", "Online:Companions",
        "Online:Quests", "Online:NPCs", "Online:Alchemy",
    }

    def _list_category_members(self, category: str, limit: int = 0, namespace: int = _ESO_NS) -> list[str]:
        """카테고리 멤버 페이지 제목 목록."""
        titles = []
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmnamespace": str(namespace),
            "cmlimit": "500",
            "cmtype": "page",
            "format": "json",
        }

        while True:
            data = self._api_get(params)
            if not data:
                break

            members = data.get("query", {}).get("categorymembers", [])
            for m in members:
                t = m["title"]
                if t in self._SKIP_TITLES:
                    continue
                titles.append(t)
                if 0 < limit <= len(titles):
                    return titles[:limit]

            cont = data.get("continue")
            if not cont:
                break
            params.update(cont)
            time.sleep(self._delay)

        return titles

    def _fetch_wikitext(self, title: str) -> str:
        """페이지의 wikitext를 가져온다."""
        data = self._api_get({
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
        })
        if not data or "error" in data:
            return ""
        return data.get("parse", {}).get("wikitext", {}).get("*", "")

    def _api_get(self, params: dict) -> dict | None:
        """MediaWiki API GET 요청."""
        try:
            resp = self._session.get(_UESP_API, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            _LOG.warning("[crawler] API error: %s", e)
            return None


    # ── Lore 크롤링 ─────────────────────────────────────

    _LORE_SKIP_TITLES = {
        "Lore:Main Page", "Lore:Index", "Lore:Books", "Lore:People",
    }

    def crawl_lore_category(
        self,
        category: str,
        *,
        limit: int = 0,
        skip_existing: bool = True,
        progress_fn=None,
    ) -> int:
        """Lore 카테고리 크롤링 (NS=130)."""
        init_db()
        cat_name = LORE_CATEGORIES.get(category, category)

        titles = self._list_category_members(cat_name, limit=limit, namespace=_LORE_NS)
        _LOG.info("[crawler] lore '%s': %d pages found", cat_name, len(titles))

        if not titles:
            return 0

        # 기존 페이지 필터링
        if skip_existing:
            with get_db() as conn:
                existing = {
                    row[0]
                    for row in conn.execute(
                        "SELECT title FROM pages WHERE category = ?", (category,)
                    ).fetchall()
                }
            titles = [t for t in titles if t not in existing]

        saved = 0
        total = len(titles)
        for i, title in enumerate(titles):
            if progress_fn:
                progress_fn(i + 1, total, title)

            if title in self._LORE_SKIP_TITLES:
                continue

            wikitext = self._fetch_wikitext(title)
            if not wikitext:
                continue
            if wikitext.strip().upper().startswith("#REDIRECT"):
                continue

            with get_db() as conn:
                conn.execute(
                    """INSERT INTO pages (title, namespace, wikitext, category, crawled_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(title) DO UPDATE SET
                           wikitext = excluded.wikitext,
                           crawled_at = excluded.crawled_at""",
                    (title, _LORE_NS, wikitext, category, datetime.utcnow().isoformat()),
                )
            saved += 1

            if self._delay > 0:
                time.sleep(self._delay)

        _LOG.info("[crawler] lore '%s': %d pages saved", cat_name, saved)
        return saved

    def crawl_lore(
        self,
        *,
        limit: int = 0,
        skip_existing: bool = True,
        progress_fn=None,
    ) -> int:
        """전체 Lore 카테고리 순회 크롤링."""
        total_saved = 0
        for cat_key in LORE_CATEGORIES:
            saved = self.crawl_lore_category(
                cat_key, limit=limit, skip_existing=skip_existing, progress_fn=progress_fn,
            )
            total_saved += saved
        _LOG.info("[crawler] lore total: %d pages saved", total_saved)
        return total_saved


# ── CLI 진입점 ──────────────────────────────────────────

def main():
    """커맨드라인에서 크롤링 실행."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    all_choices = list(CATEGORIES.keys()) + ["quests", "lore", "all"] + list(LORE_CATEGORIES.keys())
    parser = argparse.ArgumentParser(description="UESP ESO Crawler")
    parser.add_argument("category", choices=all_choices,
                        help="크롤링 카테고리 (quests=서브카테고리 재귀, lore=전체 Lore)")
    parser.add_argument("--limit", type=int, default=0, help="최대 페이지 수 (0=무제한)")
    parser.add_argument("--delay", type=float, default=0.5, help="요청 간 대기 초")
    parser.add_argument("--force", action="store_true", help="기존 페이지도 다시 크롤링")
    args = parser.parse_args()

    crawler = UESPCrawler(delay=args.delay)

    def progress(cur, total, title):
        try:
            print(f"  [{cur}/{total}] {title}")
        except UnicodeEncodeError:
            print(f"  [{cur}/{total}] {title.encode('ascii', 'replace').decode()}")

    if args.category == "all":
        categories = list(CATEGORIES.keys()) + ["quests"]
    else:
        categories = [args.category]

    total_saved = 0

    for cat in categories:
        print(f"\n=== Crawling: {cat} ===")
        if cat == "quests":
            saved = crawler.crawl_quests(
                limit=args.limit,
                skip_existing=not args.force,
                progress_fn=progress,
            )
        elif cat == "lore":
            saved = crawler.crawl_lore(
                limit=args.limit,
                skip_existing=not args.force,
                progress_fn=progress,
            )
        elif cat in LORE_CATEGORIES:
            saved = crawler.crawl_lore_category(
                cat,
                limit=args.limit,
                skip_existing=not args.force,
                progress_fn=progress,
            )
        else:
            saved = crawler.crawl_category(
                cat,
                limit=args.limit,
                skip_existing=not args.force,
                progress_fn=progress,
            )
        total_saved += saved
        print(f"  -> {saved} pages saved")

    print(f"\nTotal: {total_saved} pages saved")


if __name__ == "__main__":
    main()
