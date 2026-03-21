"""
Entity Linker — 도메인 간 관계 테이블 빌드.

Phase 1: quest_npcs, zone_dungeons, dungeon_sets 보강, alchemy 조합 매트릭스.
"""
from __future__ import annotations

import logging
import re

from pipeline.db import get_db, init_db

_LOG = logging.getLogger(__name__)


# ── Quest ↔ NPC 링킹 ──────────────────────────────────

def _clean_npc_name(giver: str) -> str:
    """퀘스트 giver 필드에서 NPC 이름만 추출.

    예: 'Maj al-Ragath at the Undaunted Enclave' → 'Maj al-Ragath'
        'Captain Rana in Bleakrock Village' → 'Captain Rana'
    """
    if not giver or not giver.strip():
        return ""

    name = giver.strip()
    # 위치 정보 분리
    for sep in (" at ", " in ", " near ", " outside ", " inside ", " on ", " within "):
        idx = name.lower().find(sep)
        if idx > 2:  # 최소 3글자 이름
            name = name[:idx].strip()
            break

    # 괄호 안 부가 정보 제거: "Name (location)"
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    # 남은 마크업 정제
    name = re.sub(r"[*#\[\]{}]", "", name).strip()

    return name if len(name) > 1 else ""


def build_quest_npcs() -> int:
    """퀘스트 giver → NPC 관계 테이블 빌드."""
    init_db()

    with get_db() as conn:
        conn.execute("DELETE FROM quest_npcs")

        rows = conn.execute(
            "SELECT id, giver FROM quests WHERE giver != ''"
        ).fetchall()

        # NPC 이름 셋 (빠른 매칭용)
        npc_rows = conn.execute("SELECT name FROM npcs").fetchall()
        npc_names = {r["name"].lower(): r["name"] for r in npc_rows}

        inserted = 0
        for row in rows:
            quest_id = row["id"]
            raw_name = _clean_npc_name(row["giver"])
            if not raw_name:
                continue

            # 정확 매칭 시도
            matched = npc_names.get(raw_name.lower())
            if not matched:
                # 부분 매칭: NPC 테이블에 giver 이름이 포함된 경우
                for npc_lower, npc_orig in npc_names.items():
                    if raw_name.lower() in npc_lower or npc_lower in raw_name.lower():
                        matched = npc_orig
                        break

            final_name = matched or raw_name
            conn.execute(
                "INSERT INTO quest_npcs (quest_id, npc_name, role) VALUES (?, ?, 'giver')",
                (quest_id, final_name),
            )
            inserted += 1

    _LOG.info("[linker] quest_npcs: %d links", inserted)
    return inserted


# ── Zone ↔ Dungeon 링킹 ───────────────────────────────

def build_zone_dungeons() -> int:
    """던전의 zone 필드로 zone_dungeons 관계 빌드."""
    init_db()

    with get_db() as conn:
        conn.execute("DELETE FROM zone_dungeons")

        dungeons = conn.execute(
            "SELECT id, zone FROM dungeons WHERE zone != ''"
        ).fetchall()
        zones = conn.execute("SELECT id, name FROM zones").fetchall()
        zone_map = {r["name"].lower(): r["id"] for r in zones}

        inserted = 0
        for d in dungeons:
            zone_id = zone_map.get(d["zone"].lower())
            if zone_id:
                conn.execute(
                    "INSERT OR IGNORE INTO zone_dungeons (zone_id, dungeon_id) VALUES (?, ?)",
                    (zone_id, d["id"]),
                )
                inserted += 1

    _LOG.info("[linker] zone_dungeons: %d links", inserted)
    return inserted


# ── Dungeon ↔ Set 보강 ─────────────────────────────────

def enrich_dungeon_sets() -> int:
    """sets.location → dungeon_sets 역방향 매칭으로 보강."""
    init_db()

    with get_db() as conn:
        # 기존 dungeon_sets 링크
        existing = set()
        for r in conn.execute("SELECT dungeon_id, set_name FROM dungeon_sets").fetchall():
            existing.add((r["dungeon_id"], r["set_name"]))

        dungeons = conn.execute("SELECT id, name FROM dungeons").fetchall()
        sets = conn.execute("SELECT name, location FROM sets WHERE location != ''").fetchall()

        inserted = 0
        for d in dungeons:
            d_name_lower = d["name"].lower()
            for s in sets:
                if d_name_lower in s["location"].lower():
                    key = (d["id"], s["name"])
                    if key not in existing:
                        conn.execute(
                            "INSERT INTO dungeon_sets (dungeon_id, set_name) VALUES (?, ?)",
                            (d["id"], s["name"]),
                        )
                        existing.add(key)
                        inserted += 1

    _LOG.info("[linker] dungeon_sets enriched: +%d links", inserted)
    return inserted


# ── Alchemy 조합 매트릭스 ──────────────────────────────

def build_alchemy_matrix() -> int:
    """연금술 재료 조합 매트릭스 빌드."""
    init_db()

    with get_db() as conn:
        conn.execute("DELETE FROM alchemy_effects")
        conn.execute("DELETE FROM reagent_effects")
        conn.execute("DELETE FROM alchemy_combinations")

        reagents = conn.execute(
            "SELECT id, name, effect1, effect2, effect3, effect4 FROM alchemy_reagents"
        ).fetchall()

        if not reagents:
            _LOG.warning("[linker] no alchemy reagents found")
            return 0

        # 1. 모든 고유 효과 수집 → alchemy_effects
        all_effects: set[str] = set()
        reagent_effects_list: list[tuple[int, str, int]] = []  # (reagent_id, effect, slot)

        for r in reagents:
            for slot, col in enumerate(["effect1", "effect2", "effect3", "effect4"], 1):
                eff = r[col].strip()
                if eff:
                    all_effects.add(eff)
                    reagent_effects_list.append((r["id"], eff, slot))

        effect_id_map: dict[str, int] = {}
        for eff_name in sorted(all_effects):
            cursor = conn.execute(
                "INSERT INTO alchemy_effects (name) VALUES (?)", (eff_name,)
            )
            effect_id_map[eff_name] = cursor.lastrowid

        # 2. reagent_effects 삽입
        for reagent_id, eff_name, slot in reagent_effects_list:
            eff_id = effect_id_map[eff_name]
            conn.execute(
                "INSERT OR IGNORE INTO reagent_effects (reagent_id, effect_id, slot) VALUES (?, ?, ?)",
                (reagent_id, eff_id, slot),
            )

        # 3. 조합 계산 — 공유 효과 있는 재료 쌍
        # 재료별 효과 셋
        reagent_effect_sets: dict[int, set[str]] = {}
        for reagent_id, eff_name, _ in reagent_effects_list:
            reagent_effect_sets.setdefault(reagent_id, set()).add(eff_name)

        combo_count = 0
        reagent_ids = sorted(reagent_effect_sets.keys())
        for i in range(len(reagent_ids)):
            for j in range(i + 1, len(reagent_ids)):
                r1, r2 = reagent_ids[i], reagent_ids[j]
                shared = reagent_effect_sets[r1] & reagent_effect_sets[r2]
                for eff in shared:
                    conn.execute(
                        "INSERT OR IGNORE INTO alchemy_combinations (reagent1_id, reagent2_id, shared_effect) VALUES (?, ?, ?)",
                        (r1, r2, eff),
                    )
                    combo_count += 1

    _LOG.info("[linker] alchemy: %d effects, %d combinations",
              len(all_effects), combo_count)
    return combo_count


# ── 전체 빌드 ─────────────────────────────────────────

def build_all() -> dict[str, int]:
    """모든 관계 테이블 빌드."""
    results = {}
    results["quest_npcs"] = build_quest_npcs()
    results["zone_dungeons"] = build_zone_dungeons()
    results["dungeon_sets_enriched"] = enrich_dungeon_sets()
    results["alchemy_combinations"] = build_alchemy_matrix()
    return results


# ── CLI ───────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Entity Linker — build relationship tables")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "quest_npcs", "zone_dungeons", "dungeon_sets", "alchemy"],
        help="빌드 대상",
    )
    args = parser.parse_args()

    if args.target == "all":
        results = build_all()
        for k, v in results.items():
            print(f"  {k}: {v}")
    elif args.target == "quest_npcs":
        print(f"  quest_npcs: {build_quest_npcs()}")
    elif args.target == "zone_dungeons":
        print(f"  zone_dungeons: {build_zone_dungeons()}")
    elif args.target == "dungeon_sets":
        print(f"  dungeon_sets: {enrich_dungeon_sets()}")
    elif args.target == "alchemy":
        print(f"  alchemy_combinations: {build_alchemy_matrix()}")


if __name__ == "__main__":
    main()
