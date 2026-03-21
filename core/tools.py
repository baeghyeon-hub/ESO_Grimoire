"""
Tool 함수 팩토리 — LLM이 호출하는 도구 함수를 생성.

각 팩토리 함수는 config를 받아 실제 tool 호출 시 실행될 클로저를 반환한다.
검색 쿼리 해석 로직(노이즈 제거, 다중 전략 resolve)도 여기서 처리.
"""
from __future__ import annotations

import logging
from functools import lru_cache

_LOG = logging.getLogger(__name__)

# ── 검색 결과 캐시 (중복 쿼리 방지) ─────────────────────

_search_cache: dict[str, str] = {}
_CACHE_MAX = 50

# ── 검색 쿼리 헬퍼 ────────────────────────────────────────

_NOISE_WORDS = {
    "mechanics", "mechanic", "guide", "how", "to", "get", "find", "where",
    "what", "is", "the", "a", "an", "about", "info", "information",
    "hard", "mode", "hardmode", "veteran", "normal", "boss", "bosses",
    "drop", "drops", "location", "locations", "build", "best",
    "set", "gear", "armor", "weapon", "skill", "skills",
    "bonus", "bonuses", "piece", "pieces", "effect", "effects",
    "pvp", "pve", "dps", "tank", "healer", "recommend",
}


def _simplify_query(query: str) -> str:
    """검색 쿼리에서 노이즈 단어를 제거하고 핵심 키워드만 반환."""
    words = query.strip().split()
    core = [w for w in words if w.lower() not in _NOISE_WORDS]
    return " ".join(core) if core else query.strip()


def _resolve_query(query: str, cfg: dict) -> dict | None:
    """쿼리를 여러 전략으로 해결. 성공하면 lookup 결과 반환, 실패면 None."""
    from core.uesp_client import lookup, get_client

    bad_prefixes = ("Online:Update ", "Online:Patch")

    # 1차: 원본 쿼리
    result = lookup(query, cfg)
    title = result.get("resolvedTitle", "")
    if result.get("found") and not title.startswith(bad_prefixes):
        return result

    # 2차: 노이즈 제거
    simplified = _simplify_query(query)
    if simplified != query.strip():
        _LOG.info("[search] retry simplified: %r -> %r", query, simplified)
        result = lookup(simplified, cfg)
        title = result.get("resolvedTitle", "")
        if result.get("found") and not title.startswith(bad_prefixes):
            return result

    # 3차: UESP search API → 첫 결과로 자동 lookup
    uesp_cfg = cfg.get("uesp_lookup", {})
    worker_url = uesp_cfg.get("worker_url", "").strip()
    if worker_url:
        client = get_client(worker_url)
        search_results = client.search(query, limit=3)
        hits = search_results.get("results", [])
        for hit in hits:
            hit_title = hit.get("title", "")
            if not hit_title or hit_title.startswith(bad_prefixes):
                continue
            _LOG.info("[search] auto-resolve via search API: %r", hit_title)
            result = lookup(hit_title, cfg)
            if result.get("found") and result.get("extract"):
                return result

    return None


# ── Tool 팩토리: uesp_search ──────────────────────────────

def make_search_fn(cfg: dict):
    """UESP 워커를 호출하는 검색 함수 생성. 이미지도 자동 포함."""
    def search(*, query: str) -> str:
        from core.uesp_client import fetch_page_images

        # 캐시 확인
        cache_key = f"search:{query.lower().strip()}"
        if cache_key in _search_cache:
            _LOG.info("[search] cache hit: %r", query)
            return _search_cache[cache_key]

        result = _resolve_query(query, cfg)
        if not result:
            return f"No results found for '{query}' on UESP."

        title = result.get("resolvedTitle", "")
        extract = result.get("extract", "")
        url = result.get("url", "")

        if not extract:
            return f"Page '{title}' found but no content available."

        # 텍스트 + 이미지 결과 구성
        text = f"Title: {title}\nURL: {url}\n\n{extract[:12000]}"

        try:
            images = fetch_page_images(title, thumb_width=400, max_images=3)
            if images:
                img_lines = ["\n\nIMAGES:"]
                for img in images:
                    caption = img["title"].replace("File:ON-", "").rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
                    img_lines.append(f"{img['thumb']}|{img['url']}|{caption}")
                text += "\n".join(img_lines)
        except Exception as e:
            _LOG.warning("[search] image fetch failed: %s", e)

        # 캐시 저장
        if len(_search_cache) >= _CACHE_MAX:
            # 가장 오래된 항목 제거
            _search_cache.pop(next(iter(_search_cache)))
        _search_cache[cache_key] = text

        return text
    return search


# ── Tool 팩토리: lore_search ──────────────────────────────

def make_lore_search_fn(cfg: dict):
    """Lore 시맨틱 검색 함수 생성. 벡터 + BM25 하이브리드."""
    def lore_search(*, query: str) -> str:
        from pipeline.lore_search import search_lore
        from core.uesp_client import fetch_page_images

        cache_key = f"lore:{query.lower().strip()}"
        if cache_key in _search_cache:
            _LOG.info("[lore] cache hit: %r", query)
            return _search_cache[cache_key]

        results = search_lore(query, cfg, limit=5)
        if not results:
            return f"No lore found for '{query}'. Try uesp_search for wiki lookup."

        lines = [f"Found {len(results)} lore entries for '{query}':\n"]
        lines.append("IMPORTANT: Only cite these exact source titles below. Do NOT invent book or page names.\n")
        seen_titles = set()
        for r in results:
            title = r.get("page_title", "")
            section = r.get("section", "")
            text = r.get("text", "")[:800]
            header = f"[Source: {title} > {section}]" if section else f"[Source: {title}]"
            lines.append(header)
            lines.append(text)
            lines.append("")
            if title:
                seen_titles.add(title)

        # Fetch images from top lore pages
        all_images = []
        for page_title in list(seen_titles)[:3]:
            try:
                images = fetch_page_images(page_title, thumb_width=400, max_images=2)
                all_images.extend(images)
            except Exception:
                pass
        if all_images:
            lines.append("\nIMAGES:")
            for img in all_images[:4]:
                caption = img["title"].replace("File:", "").rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
                lines.append(f"{img['thumb']}|{img['url']}|{caption}")

        text = "\n".join(lines)
        if len(_search_cache) >= _CACHE_MAX:
            _search_cache.pop(next(iter(_search_cache)))
        _search_cache[cache_key] = text
        return text

    return lore_search


# ── Tool 팩토리: uesp_db ──────────────────────────────────

def make_db_fn():
    """로컬 DB 쿼리 함수 생성. 세트 + 스킬 + 던전 + 존 + 퀘스트 + NPC + 연금술 지원."""
    def db_query(*, action: str, query: str = "", set_type: str = "",
                 armor_type: str = "", location: str = "",
                 skill_line: str = "", zone: str = "",
                 quest_type: str = "", dungeon_type: str = "") -> str:
        from pipeline.db import get_set_by_name, search_sets, filter_sets, search_fts, init_db

        # 캐시 확인
        cache_key = f"db:{action}:{query}:{set_type}:{armor_type}:{location}:{zone}".lower()
        if cache_key in _search_cache:
            _LOG.info("[db] cache hit: %s", cache_key[:60])
            return _search_cache[cache_key]

        try:
            init_db()
        except Exception as e:
            return f"DB init error: {e}"

        result = _dispatch_db(action, query, set_type, armor_type, location,
                              get_set_by_name, search_sets, filter_sets, search_fts,
                              skill_line=skill_line, zone=zone,
                              quest_type=quest_type, dungeon_type=dungeon_type)

        # 성공 결과만 캐시
        if not result.startswith("Error:") and not result.startswith("Unknown"):
            if len(_search_cache) >= _CACHE_MAX:
                _search_cache.pop(next(iter(_search_cache)))
            _search_cache[cache_key] = result

        return result

    return db_query


def _dispatch_db(action, query, set_type, armor_type, location,
                 get_set_by_name, search_sets, filter_sets, search_fts,
                 *, skill_line="", zone="", quest_type="", dungeon_type="") -> str:
    """DB action 디스패치 — 모든 도메인 지원."""
    from pipeline.db import _get_conn

    # ── Sets ──
    if action == "get_set":
        if not query:
            return "Error: 'query' (set name) is required for get_set."
        data = get_set_by_name(query)
        if not data:
            return f"Set '{query}' not found in DB. Try search_sets or uesp_search."
        lines = [
            f"Set: {data['name']}",
            f"Type: {data['set_type'] or 'unknown'}",
            f"Armor: {data['armor_type'] or 'any'}",
            f"Location: {data['location'] or 'unknown'}",
            f"DLC: {data['dlc'] or 'base game'}",
            f"Craftable: {'Yes' if data['craftable'] else 'No'}",
            f"Description: {data['description']}",
            "", "Bonuses:",
        ]
        for b in data.get("bonuses", []):
            lines.append(f"  ({b['piece_count']} items) {b['bonus_text']}")
        return "\n".join(lines)

    elif action == "search_sets":
        if not query:
            return "Error: 'query' is required for search_sets."
        results = search_sets(query, limit=10)
        if not results:
            return f"No sets matching '{query}'. Try uesp_search."
        lines = [f"Found {len(results)} sets matching '{query}':"]
        for s in results:
            lines.append(f"  - {s['name']} ({s['set_type'] or 'unknown'}, {s['location'] or '?'})")
        return "\n".join(lines)

    elif action == "filter_sets":
        results = filter_sets(set_type=set_type, armor_type=armor_type, location=location, limit=20)
        if not results:
            return "No sets matching the filter criteria."
        lines = [f"Found {len(results)} sets:"]
        for s in results:
            lines.append(f"  - {s['name']} ({s['set_type']}, {s['armor_type'] or 'any'}, {s['location'] or '?'})")
        return "\n".join(lines)

    elif action == "search_by_stat":
        if not query:
            return "Error: 'query' (stat type like 'Critical Chance') is required."
        from pipeline.db import search_by_stat
        results = search_by_stat(query, limit=20)
        if not results:
            return f"No sets with stat '{query}'."
        grouped: dict[str, list[str]] = {}
        for r in results:
            name = r["name"]
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(f"({r['piece_count']}pc) {r['bonus_text']}")
        lines = [f"Found {len(grouped)} sets with '{query}':"]
        for name, bonuses in list(grouped.items())[:15]:
            lines.append(f"  {name}:")
            for b in bonuses:
                lines.append(f"    {b}")
        return "\n".join(lines)

    # ── Skills ──
    elif action == "get_skill":
        if not query:
            return "Error: 'query' (skill name) is required."
        conn = _get_conn()
        row = conn.execute("SELECT * FROM skills WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                           (query,)).fetchone()
        if not row:
            # 부분 매칭
            row = conn.execute("SELECT * FROM skills WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                               (f"%{query}%",)).fetchone()
        if not row:
            return f"Skill '{query}' not found. Try search_skills."
        lines = [
            f"Skill: {row['name']}",
            f"Skill Line: {row['skill_line']}",
            f"Cost: {row['cost'] or 'None'}",
            f"Cast Time: {row['cast_time'] or 'Instant'}",
            f"Target: {row['target'] or 'N/A'}",
            f"Range: {row['range_info'] or 'N/A'}",
            f"Description: {row['description']}",
        ]
        if row['morph1_name']:
            lines.append(f"\nMorph 1 - {row['morph1_name']}: {row['morph1_desc']}")
        if row['morph2_name']:
            lines.append(f"Morph 2 - {row['morph2_name']}: {row['morph2_desc']}")
        return "\n".join(lines)

    elif action == "search_skills":
        if not query and not skill_line:
            return "Error: 'query' or 'skill_line' required."
        conn = _get_conn()
        if skill_line:
            rows = conn.execute(
                "SELECT name, skill_line, cost, morph1_name, morph2_name FROM skills WHERE skill_line LIKE ? COLLATE NOCASE ORDER BY name LIMIT 20",
                (f"%{skill_line}%",)).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, skill_line, cost, morph1_name, morph2_name FROM skills WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT 15",
                (f"%{query}%",)).fetchall()
        if not rows:
            return f"No skills found. Try uesp_search."
        lines = [f"Found {len(rows)} skills:"]
        for r in rows:
            morphs = f" → {r['morph1_name']}/{r['morph2_name']}" if r['morph1_name'] else ""
            lines.append(f"  - {r['name']} ({r['skill_line']}) {r['cost']}{morphs}")
        return "\n".join(lines)

    # ── Dungeons ──
    elif action == "get_dungeon":
        if not query:
            return "Error: 'query' (dungeon name) is required."
        conn = _get_conn()
        row = conn.execute("SELECT * FROM dungeons WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                           (f"%{query}%",)).fetchone()
        if not row:
            return f"Dungeon '{query}' not found."
        d = dict(row)
        lines = [
            f"Dungeon: {d['name']}",
            f"Type: {d['dungeon_type']}",
            f"Zone: {d['zone'] or 'N/A'}",
            f"DLC: {d['dlc'] or 'base game'}",
            f"Group Size: {d['group_size']}",
            f"Min Level: {d['min_level']}",
            f"Description: {d['description']}",
        ]
        bosses = conn.execute(
            "SELECT boss_name, boss_type, strategy FROM dungeon_bosses WHERE dungeon_id = ? ORDER BY boss_type DESC, boss_name",
            (d['id'],)).fetchall()
        if bosses:
            lines.append("\nBosses:")
            for b in bosses:
                strat = f" — {b['strategy'][:200]}" if b['strategy'] else ""
                lines.append(f"  [{b['boss_type']}] {b['boss_name']}{strat}")
        sets = conn.execute("SELECT set_name FROM dungeon_sets WHERE dungeon_id = ?",
                            (d['id'],)).fetchall()
        if sets:
            lines.append("\nSets:")
            for s in sets:
                lines.append(f"  - {s['set_name']}")
        return "\n".join(lines)

    elif action == "search_dungeons":
        conn = _get_conn()
        conditions, params = [], []
        if query:
            conditions.append("name LIKE ? COLLATE NOCASE")
            params.append(f"%{query}%")
        if zone:
            conditions.append("zone LIKE ? COLLATE NOCASE")
            params.append(f"%{zone}%")
        if dungeon_type:
            conditions.append("dungeon_type LIKE ? COLLATE NOCASE")
            params.append(f"%{dungeon_type}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(f"SELECT name, dungeon_type, zone, dlc FROM dungeons WHERE {where} ORDER BY name LIMIT 20",
                            params).fetchall()
        if not rows:
            return "No dungeons found."
        lines = [f"Found {len(rows)} dungeons:"]
        for r in rows:
            lines.append(f"  - {r['name']} ({r['dungeon_type']}, {r['zone'] or '?'}, {r['dlc'] or 'base'})")
        return "\n".join(lines)

    # ── Zones ──
    elif action == "get_zone":
        if not query:
            return "Error: 'query' (zone name) is required."
        conn = _get_conn()
        row = conn.execute("SELECT * FROM zones WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                           (f"%{query}%",)).fetchone()
        if not row:
            return f"Zone '{query}' not found."
        z = dict(row)
        lines = [
            f"Zone: {z['name']}",
            f"Type: {z['zone_type']}",
            f"Alliance: {z['alliance'] or 'N/A'}",
            f"DLC: {z['dlc'] or 'base game'}",
            f"Hub: {z['hub'] or 'N/A'}",
            f"Wayshrines: {z['wayshrines']}, Delves: {z['delves']}, World Bosses: {z['world_bosses']}",
            f"Skyshards: {z['skyshards']}, Set Stations: {z['set_stations']}",
            f"Public Dungeons: {z['public_dungeons']}, Group Dungeons: {z['group_dungeons']}",
            f"Quests: {z['quests']}",
            f"Description: {z['description']}",
        ]
        return "\n".join(lines)

    elif action == "search_zones":
        conn = _get_conn()
        if query:
            rows = conn.execute("SELECT name, alliance, dlc, skyshards, world_bosses FROM zones WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT 20",
                                (f"%{query}%",)).fetchall()
        else:
            rows = conn.execute("SELECT name, alliance, dlc, skyshards, world_bosses FROM zones ORDER BY name LIMIT 50").fetchall()
        if not rows:
            return "No zones found."
        lines = [f"Found {len(rows)} zones:"]
        for r in rows:
            lines.append(f"  - {r['name']} ({r['alliance'] or 'N/A'}, {r['dlc'] or 'base'}) shards:{r['skyshards']} wb:{r['world_bosses']}")
        return "\n".join(lines)

    # ── Quests ──
    elif action == "get_quest":
        if not query:
            return "Error: 'query' (quest name) is required."
        conn = _get_conn()
        row = conn.execute("SELECT * FROM quests WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                           (f"%{query}%",)).fetchone()
        if not row:
            return f"Quest '{query}' not found."
        q = dict(row)
        lines = [
            f"Quest: {q['name']}",
            f"Type: {q['quest_type'] or 'N/A'}",
            f"Zone: {q['zone'] or 'N/A'}",
            f"Quest Giver: {q['giver'] or 'N/A'}",
            f"Location: {q['location'] or 'N/A'}",
            f"DLC: {q['dlc'] or 'base game'}",
            f"Skill Point: {'Yes' if q['skill_point'] else 'No'}",
            f"Description: {q['description']}",
        ]
        # Quest chain (prev/next)
        prev_q = q.get('prev_quest', '')
        next_q = q.get('next_quest', '')
        if prev_q or next_q:
            lines.append("")
            lines.append("Quest Chain:")
            if prev_q:
                lines.append(f"  ← Previous: {prev_q}")
            lines.append(f"  ● Current: {q['name']}")
            if next_q:
                lines.append(f"  → Next: {next_q}")
        return "\n".join(lines)

    elif action == "search_quests":
        conn = _get_conn()
        conditions, params = [], []
        if query:
            conditions.append("name LIKE ? COLLATE NOCASE")
            params.append(f"%{query}%")
        if zone:
            conditions.append("zone LIKE ? COLLATE NOCASE")
            params.append(f"%{zone}%")
        if quest_type:
            conditions.append("quest_type LIKE ? COLLATE NOCASE")
            params.append(f"%{quest_type}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(f"SELECT name, quest_type, zone, giver, skill_point FROM quests WHERE {where} ORDER BY name LIMIT 20",
                            params).fetchall()
        if not rows:
            return "No quests found."
        lines = [f"Found {len(rows)} quests:"]
        for r in rows:
            sp = " [SP]" if r['skill_point'] else ""
            lines.append(f"  - {r['name']} ({r['quest_type'] or '?'}, {r['zone'] or '?'}) giver: {r['giver'] or '?'}{sp}")
        return "\n".join(lines)

    # ── NPCs ──
    elif action == "search_npcs":
        if not query and not zone:
            return "Error: 'query' or 'zone' required."
        conn = _get_conn()
        conditions, params = [], []
        if query:
            conditions.append("name LIKE ? COLLATE NOCASE")
            params.append(f"%{query}%")
        if zone:
            conditions.append("(zone LIKE ? COLLATE NOCASE OR location LIKE ? COLLATE NOCASE)")
            params.extend([f"%{zone}%", f"%{zone}%"])
        where = " AND ".join(conditions)
        rows = conn.execute(f"SELECT name, race, gender, reaction, location FROM npcs WHERE {where} ORDER BY name LIMIT 20",
                            params).fetchall()
        if not rows:
            return f"No NPCs found."
        lines = [f"Found {len(rows)} NPCs:"]
        for r in rows:
            lines.append(f"  - {r['name']} ({r['race']} {r['gender']}, {r['reaction']}) @ {r['location'] or '?'}")
        return "\n".join(lines)

    # ── Companions ──
    elif action == "get_companion":
        if not query:
            return "Error: 'query' (companion name) is required."
        conn = _get_conn()
        row = conn.execute("SELECT * FROM companions WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                           (f"%{query}%",)).fetchone()
        if not row:
            return f"Companion '{query}' not found."
        c = dict(row)
        lines = [
            f"Companion: {c['name']}",
            f"Race: {c['race']}, Gender: {c['gender']}",
            f"Location: {c['location']}",
            f"DLC: {c['dlc'] or 'base game'}",
            f"Perk: {c['perk']}",
            f"Description: {c['description']}",
        ]
        return "\n".join(lines)

    # ── Alchemy ──
    elif action == "search_alchemy":
        if not query:
            return "Error: 'query' (reagent name or effect) is required."
        conn = _get_conn()
        # 이름으로 검색
        rows = conn.execute(
            "SELECT * FROM alchemy_reagents WHERE name LIKE ? COLLATE NOCASE LIMIT 10",
            (f"%{query}%",)).fetchall()
        # 효과로도 검색
        if not rows:
            rows = conn.execute(
                """SELECT * FROM alchemy_reagents WHERE
                   effect1 LIKE ? COLLATE NOCASE OR effect2 LIKE ? COLLATE NOCASE OR
                   effect3 LIKE ? COLLATE NOCASE OR effect4 LIKE ? COLLATE NOCASE
                   LIMIT 15""",
                (f"%{query}%",) * 4).fetchall()
        if not rows:
            return f"No alchemy data for '{query}'."
        lines = [f"Found {len(rows)} reagents:"]
        for r in rows:
            effects = " / ".join(filter(None, [r['effect1'], r['effect2'], r['effect3'], r['effect4']]))
            lines.append(f"  - {r['name']}: {effects}")
        return "\n".join(lines)

    # ── Quest Chain ──
    elif action == "get_quest_chain":
        if not query:
            return "Error: 'query' (quest name) is required."
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM quests WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
            (f"%{query}%",)).fetchone()
        if not row:
            return f"Quest '{query}' not found."
        q = dict(row)
        chain: list[dict] = []

        # 역방향 탐색 (prev)
        prev_name = q.get("prev_quest", "")
        visited = {q["name"]}
        while prev_name and prev_name not in visited:
            visited.add(prev_name)
            pr = conn.execute(
                "SELECT name, prev_quest, next_quest, zone, quest_type FROM quests WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (prev_name,)).fetchone()
            if not pr:
                chain.insert(0, {"name": prev_name, "zone": "?", "type": "?"})
                break
            chain.insert(0, {"name": pr["name"], "zone": pr["zone"], "type": pr["quest_type"]})
            prev_name = pr["prev_quest"] or ""

        # 현재
        chain.append({"name": q["name"], "zone": q["zone"], "type": q["quest_type"], "current": True})

        # 순방향 탐색 (next)
        next_name = q.get("next_quest", "")
        while next_name and next_name not in visited:
            visited.add(next_name)
            nr = conn.execute(
                "SELECT name, prev_quest, next_quest, zone, quest_type FROM quests WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
                (next_name,)).fetchone()
            if not nr:
                chain.append({"name": next_name, "zone": "?", "type": "?"})
                break
            chain.append({"name": nr["name"], "zone": nr["zone"], "type": nr["quest_type"]})
            next_name = nr["next_quest"] or ""

        if len(chain) <= 1:
            return f"Quest '{q['name']}' has no linked quest chain."

        lines = [f"Quest Chain ({len(chain)} quests):"]
        for i, c in enumerate(chain):
            marker = "●" if c.get("current") else "○"
            lines.append(f"  {i+1}. {marker} {c['name']} ({c.get('type', '?')}, {c.get('zone', '?')})")
        return "\n".join(lines)

    # ── Alchemy Combo ──
    elif action == "search_alchemy_combo":
        if not query:
            return "Error: 'query' (effect name or reagent name) is required."
        conn = _get_conn()

        # 효과로 검색
        combos = conn.execute(
            """SELECT r1.name AS reagent1, r2.name AS reagent2, ac.shared_effect
               FROM alchemy_combinations ac
               JOIN alchemy_reagents r1 ON ac.reagent1_id = r1.id
               JOIN alchemy_reagents r2 ON ac.reagent2_id = r2.id
               WHERE ac.shared_effect LIKE ? COLLATE NOCASE
               ORDER BY ac.shared_effect, r1.name
               LIMIT 30""",
            (f"%{query}%",)).fetchall()

        if combos:
            lines = [f"Alchemy combinations for effect '{query}':"]
            for c in combos:
                lines.append(f"  {c['reagent1']} + {c['reagent2']} → {c['shared_effect']}")
            return "\n".join(lines)

        # 재료로 검색: 해당 재료가 포함된 모든 조합
        reagent = conn.execute(
            "SELECT id, name FROM alchemy_reagents WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
            (f"%{query}%",)).fetchone()
        if not reagent:
            return f"No alchemy data for '{query}'."

        combos = conn.execute(
            """SELECT r1.name AS reagent1, r2.name AS reagent2, ac.shared_effect
               FROM alchemy_combinations ac
               JOIN alchemy_reagents r1 ON ac.reagent1_id = r1.id
               JOIN alchemy_reagents r2 ON ac.reagent2_id = r2.id
               WHERE ac.reagent1_id = ? OR ac.reagent2_id = ?
               ORDER BY ac.shared_effect
               LIMIT 40""",
            (reagent["id"], reagent["id"])).fetchall()

        if not combos:
            return f"No combinations found for '{reagent['name']}'."

        lines = [f"Combinations with {reagent['name']}:"]
        for c in combos:
            partner = c["reagent2"] if c["reagent1"] == reagent["name"] else c["reagent1"]
            lines.append(f"  + {partner} → {c['shared_effect']}")
        return "\n".join(lines)

    # ── Full-text search ──
    elif action == "search_text":
        if not query:
            return "Error: 'query' is required for search_text."
        results = search_fts(query, limit=10)
        if not results:
            return f"No pages matching '{query}'."
        lines = [f"Found {len(results)} pages:"]
        for r in results:
            lines.append(f"  - {r['title']}: {r['snippet']}")
        return "\n".join(lines)

    return (f"Unknown action: {action}. Available: get_set, search_sets, filter_sets, search_by_stat, "
            f"get_skill, search_skills, get_dungeon, search_dungeons, get_zone, search_zones, "
            f"get_quest, search_quests, get_quest_chain, search_npcs, get_companion, "
            f"search_alchemy, search_alchemy_combo, search_text.")
