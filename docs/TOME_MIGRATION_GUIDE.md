# ToME (Tales of Maj'Eyal) — Migration Guide from Grimoire

> Grimoire ESO 파이프라인을 ToME 위키 기반 AI 챗봇으로 포팅하기 위한 설계 문서.
> 기존 아키텍처의 ~60%를 재사용하고, 나머지를 ToME 도메인에 맞게 새로 작성한다.

---

## 1. 재사용 파일 (그대로 복사)

게임에 의존하지 않는 범용 모듈. 수정 없이 가져간다.

### Core Engine
| File | Role |
|------|------|
| `core/agent.py` | LLM 대화 엔진 (메시지 히스토리, 도구 루프) |
| `core/providers.py` | 멀티 프로바이더 추상화 (Claude, Gemini, GPT, Ollama) |
| `core/config.py` | 설정 관리 (API 키, 언어, 모델 선택) |
| `core/cache.py` | LRU 캐시 (파일 기반) |
| `core/logging_setup.py` | 로깅 설정 |

### Pipeline (Embedding & Vector)
| File | Role |
|------|------|
| `pipeline/embedder.py` | Voyage AI 임베딩 (voyage-4, 배치 처리) |
| `pipeline/vector_store.py` | LanceDB 벡터 저장소 (파일 기반) |
| `pipeline/chunk_cleanup.py` | 청크 품질 정리 (노이즈 제거) — 패턴만 수정 |

### Frontend (UI Components)
| File | Role |
|------|------|
| `src/lib/api.js` | FastAPI HTTP 클라이언트 |
| `src/lib/channel.js` | Tauri IPC 통신 |
| `src/lib/storage.js` | localStorage 래퍼 |
| `src/lib/imageStore.js` | 이미지 뷰어 상태 |
| `src/lib/windowManager.js` | Tauri 동적 윈도우 |
| `src/panel/ChatList.svelte` | 메시지 스크롤 컨테이너 |
| `src/panel/InputBar.svelte` | 텍스트 입력 + 전송 |

### Config & Build
| File | Role |
|------|------|
| `src-tauri/tauri.conf.json` | Tauri 빌드 설정 (앱 이름, 아이콘만 변경) |
| `package.json` | 빌드 스크립트 (앱 이름만 변경) |
| `config.example.json` | 배포용 설정 템플릿 |

---

## 2. 수정 파일 (포크 후 수정)

기존 구조를 유지하되, ToME 도메인에 맞게 내용을 교체한다.

### 2.1 `pipeline/crawler.py` → ToME 위키 크롤러
```python
# 변경 사항:
# - UESP API URL → te4.org 위키 API URL
# - ESO_CATEGORIES → TOME_CATEGORIES
# - LORE_CATEGORIES → TOME_LORE_CATEGORIES (있다면)

TOME_CATEGORIES = {
    "classes":       "Classes",        # Berserker, Archmage, Rogue, ...
    "talents":       "Talents",        # 스킬 트리
    "zones":         "Zones",          # 던전/지역
    "creatures":     "Creatures",      # 몬스터
    "items":         "Items",          # 아이템/아티팩트
    "races":         "Races",          # 종족
    "prodigies":     "Prodigies",      # 특수 능력
    "egos":          "Egos",           # 아이템 접사
    "lore":          "Lore",           # 세계관
    "achievements":  "Achievements",   # 업적
    "events":        "Events",         # 인게임 이벤트
}
```

**주의**: te4.org 위키가 MediaWiki 기반인지 확인 필요.
- MediaWiki → 기존 `action=parse` API 그대로 사용
- 커스텀 위키 → BeautifulSoup HTML 파싱으로 전환

### 2.2 `pipeline/db.py` → ToME DB 스키마
```sql
-- ESO 테이블 제거, ToME 테이블 추가
CREATE TABLE classes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    type TEXT,           -- Warrior, Mage, Rogue, ...
    locked INTEGER,      -- 잠금 여부
    description TEXT
);

CREATE TABLE talents (
    id INTEGER PRIMARY KEY,
    name TEXT,
    class TEXT,          -- 어떤 클래스의 스킬인지
    tree TEXT,           -- 스킬 트리
    tier INTEGER,        -- 1~5 티어
    cost TEXT,           -- 스태미나/마나/쿨다운
    description TEXT,
    scaling TEXT          -- 레벨별 스케일링 공식
);

CREATE TABLE zones (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    tier TEXT,            -- T1~T5
    level_range TEXT,
    zone_type TEXT,       -- dungeon, overworld, special
    description TEXT
);

CREATE TABLE creatures (
    id INTEGER PRIMARY KEY,
    name TEXT,
    zone TEXT,
    rank TEXT,            -- normal, rare, boss, unique
    abilities TEXT,       -- 주요 능력
    drops TEXT            -- 드랍 아이템
);

CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    name TEXT,
    slot TEXT,            -- weapon, armor, ring, ...
    tier TEXT,
    material TEXT,
    egos TEXT,            -- 접사 목록
    unique_power TEXT,    -- 유니크 아이템 특수 효과
    description TEXT
);

CREATE TABLE prodigies (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    stat_req TEXT,        -- 필요 스탯 조건
    description TEXT
);
```

### 2.3 `pipeline/lore_search.py` → 쿼리 확장 수정
```python
_QUERY_ALIASES = {
    # ToME 한국어/약어 매핑
    "버서커": "Berserker",
    "아크메이지": "Archmage",
    "로그": "Rogue",
    "벌크": "Bulwark",
    "서머너": "Summoner",
    "네크로맨서": "Necromancer",
    "알케미스트": "Alchemist",
    "프로디지": "Prodigy Prodigies",
    "이고": "Ego",
    "아티팩트": "Artifact unique item",
    "인세인": "Insane difficulty",
    "매드니스": "Madness difficulty",
    "에다": "Eyal Arda",
    "마즈에알": "Maj'Eyal",
}
```

### 2.4 `pipeline/lore_chunker.py` → ToME 카테고리 반영
```python
_CHUNK_CATEGORIES = ("lore-%",)
_EXTRA_CHUNK_CATS = (
    "classes", "talents", "zones", "creatures",
    "items", "prodigies", "egos", "achievements",
)
```

### 2.5 `rag/query_router.py` → ToME 질의 분류
```python
# STRICT Mode 트리거:
# - 클래스 이름 감지 → DB에서 직접 조회
# - 탤런트/스킬 이름 → talents 테이블
# - 아이템/아티팩트 이름 → items 테이블
# - "파밍", "드랍", "어디서" → zones/creatures 조회

# CREATIVE Mode:
# - "빌드 추천", "로그 뭐 찍어야 돼", "인세인 공략"
# - LLM에게 Tool 권한 부여
```

### 2.6 `core/tools.py` → ToME 도구 함수
```python
# Tool 1: tome_db
#   → get_class, search_talents, get_zone, search_items
#   → get_prodigy, search_creatures

# Tool 2: tome_wiki
#   → te4.org 위키 실시간 검색 (UESP Worker 대체)

# Tool 3: lore_search
#   → 하이브리드 벡터 검색 (그대로 재사용)
```

### 2.7 `core/uesp_agent.py` → `core/tome_agent.py`
```python
# 변경 사항:
# - 시스템 프롬프트: ESO 전문가 → ToME 전문가
# - Tool 바인딩: uesp_db → tome_db
# - 위키 링크 포맷: [[Online:Name]] → [[ToME_Wiki:Name]]
# - 한국어 프롬프트: ESO 용어 → ToME 용어
```

### 2.8 Frontend 수정
| File | 변경 사항 |
|------|-----------|
| `src/lib/i18n.js` | 번역 문자열 교체 ("ESO" → "ToME", 세트→아이템, 던전→존 등) |
| `src/lib/markdown.js` | 위키 링크 URL 교체 (`en.uesp.net/wiki/Online:` → `te4.org/wiki/`) |
| `src/panel/WelcomeScreen.svelte` | "Ask me anything about ToME", 예시 질문 교체 |
| `src/panel/PanelHeader.svelte` | 앱 타이틀 변경 |
| `src/panel/SettingsDialog.svelte` | 프로바이더 목록은 동일, UI 텍스트만 |
| `src/panel/DbMissingDialog.svelte` | DB 다운로드 링크 변경 |

---

## 3. 새로 생성 파일

### 3.1 파서 (pipeline/parsers/)
```
pipeline/parsers/
├── common.py          ← 재사용 (wikitext 정제 유틸)
├── tome_classes.py    ← 새로 작성: 클래스 파서
├── tome_talents.py    ← 새로 작성: 탤런트/스킬 트리 파서
├── tome_zones.py      ← 새로 작성: 존/던전 파서
├── tome_creatures.py  ← 새로 작성: 몬스터 파서
├── tome_items.py      ← 새로 작성: 아이템/아티팩트 파서
├── tome_prodigies.py  ← 새로 작성: 프로디지 파서
└── lore.py            ← 재사용 (섹션 기반 청킹)
```

### 3.2 Characters Vault 크롤러 (선택)
```
pipeline/
├── vault_crawler.py   ← 새로 작성: te4.org/characters-vault 크롤러
├── vault_parser.py    ← 새로 작성: 캐릭터 빌드 데이터 파싱
└── vault_stats.py     ← 새로 작성: 빌드 통계 집계 (클래스별 승률, 인기 스킬 등)
```

**Characters Vault 데이터 구조 (예상):**
```sql
CREATE TABLE vault_characters (
    id INTEGER PRIMARY KEY,
    name TEXT,
    class TEXT,
    race TEXT,
    level INTEGER,
    difficulty TEXT,        -- Normal/Nightmare/Insane/Madness
    winner INTEGER,         -- 클리어 여부
    death_zone TEXT,         -- 사망 장소 (사망한 경우)
    talents_json TEXT,       -- 스킬 포인트 배분 (JSON)
    equipment_json TEXT,     -- 장착 장비 (JSON)
    prodigies TEXT,          -- 선택한 프로디지
    submitted_at TEXT
);
```

### 3.3 빌드 마스터 스크립트
```
pipeline/
├── build_tome.py      ← 새로 작성: 전체 파이프라인 오케스트레이터
│                         (crawl → parse → chunk → embed)
└── build_vault.py     ← 새로 작성: Characters Vault 전용 파이프라인
```

---

## 4. 폴더 구조 (최종)

```
Tome-Grimoire/                    (또는 Grimoire-ToME)
├── core/
│   ├── agent.py                  ← 그대로 복사
│   ├── providers.py              ← 그대로 복사
│   ├── config.py                 ← 그대로 복사 (앱 이름만 변경)
│   ├── cache.py                  ← 그대로 복사
│   ├── logging_setup.py          ← 그대로 복사
│   ├── tome_agent.py             ← 새로 작성 (uesp_agent.py 기반)
│   ├── tools.py                  ← 수정 (ToME 도구)
│   └── tome_client.py            ← 새로 작성 (te4.org API 클라이언트)
├── pipeline/
│   ├── crawler.py                ← 수정 (te4.org 위키)
│   ├── db.py                     ← 수정 (ToME 스키마)
│   ├── cleaner.py                ← 그대로 복사
│   ├── embedder.py               ← 그대로 복사
│   ├── vector_store.py           ← 그대로 복사
│   ├── lore_chunker.py           ← 수정 (카테고리 변경)
│   ├── lore_search.py            ← 수정 (쿼리 확장 매핑)
│   ├── chunk_cleanup.py          ← 수정 (패턴 변경)
│   ├── indexer.py                ← 수정 (ToME 파서 연결)
│   ├── linker.py                 ← 수정 (ToME 관계 테이블)
│   ├── build_tome.py             ← 새로 작성
│   ├── vault_crawler.py          ← 새로 작성 (선택)
│   ├── vault_parser.py           ← 새로 작성 (선택)
│   └── parsers/
│       ├── common.py             ← 그대로 복사
│       ├── lore.py               ← 그대로 복사
│       ├── tome_classes.py       ← 새로 작성
│       ├── tome_talents.py       ← 새로 작성
│       ├── tome_zones.py         ← 새로 작성
│       ├── tome_creatures.py     ← 새로 작성
│       ├── tome_items.py         ← 새로 작성
│       └── tome_prodigies.py     ← 새로 작성
├── rag/
│   └── query_router.py           ← 수정 (ToME 분류 패턴)
├── server/
│   └── main.py                   ← 수정 (엔드포인트 이름)
├── db/
│   ├── tome.db                   ← 빌드 시 생성
│   └── lore.lance/               ← 빌드 시 생성
├── src/
│   ├── lib/
│   │   ├── api.js                ← 그대로 복사
│   │   ├── channel.js            ← 그대로 복사
│   │   ├── storage.js            ← 그대로 복사
│   │   ├── i18n.js               ← 수정 (번역 문자열)
│   │   ├── markdown.js           ← 수정 (위키 링크 URL)
│   │   ├── imageStore.js         ← 그대로 복사
│   │   └── windowManager.js      ← 그대로 복사
│   ├── panel/
│   │   ├── PanelApp.svelte       ← 수정 (임포트 경로)
│   │   ├── PanelHeader.svelte    ← 수정 (타이틀)
│   │   ├── ChatList.svelte       ← 그대로 복사
│   │   ├── InputBar.svelte       ← 그대로 복사
│   │   ├── MessageBubble.svelte  ← 수정 (위키 링크)
│   │   ├── SettingsDialog.svelte ← 수정 (UI 텍스트)
│   │   ├── WelcomeScreen.svelte  ← 수정 (예시 질문)
│   │   └── DbMissingDialog.svelte← 수정 (링크)
│   └── ...
├── src-tauri/
│   └── tauri.conf.json           ← 수정 (앱 이름, 아이콘)
├── docs/
│   └── TOME_DB_ARCHITECTURE.md   ← 새로 작성
├── config.example.json           ← 수정 (앱 이름)
├── package.json                  ← 수정 (앱 이름)
└── README.md                     ← 새로 작성
```

---

## 5. 작업량 추정

| 카테고리 | 파일 수 | 예상 시간 |
|---------|---------|----------|
| 그대로 복사 | 16 | 0h |
| 수정 (도메인 교체) | 18 | 8~12h |
| 새로 작성 (파서) | 6 | 10~15h |
| 새로 작성 (Vault) | 3 | 6~8h (선택) |
| UI 테마/아이콘 | — | 2~3h |
| 테스트/디버깅 | — | 5~8h |
| **합계** | **~43** | **~31~46h** |

Characters Vault 제외 시: **~25~38h**

---

## 6. 우선순위 로드맵

### Phase 1: 위키 기반 (MVP)
1. te4.org 위키 구조 조사 (MediaWiki 여부 확인)
2. `crawler.py` 수정 → 위키 페이지 크롤링
3. `tome_classes.py`, `tome_talents.py` 파서 작성
4. DB 스키마 + 청킹 + 임베딩
5. `tome_agent.py` + 시스템 프롬프트
6. 동작 확인

### Phase 2: 검색 품질
7. 쿼리 라우터 ToME 버전
8. 쿼리 확장 (한국어/약어)
9. 청크 품질 정리

### Phase 3: Characters Vault (선택)
10. Vault 크롤러
11. 빌드 통계 집계
12. "인세인 Archmage 빌드 추천" → 실제 클리어 데이터 기반 답변

### Phase 4: 배포
13. UI 테마 변경
14. 빌드 & 인스톨러
15. README + 릴리즈

---

## 7. 핵심 차이점 요약

| | Grimoire (ESO) | Grimoire (ToME) |
|---|---|---|
| 데이터 소스 | UESP Wiki (MediaWiki) | te4.org Wiki + Characters Vault |
| 주요 테이블 | sets, quests, skills, dungeons | classes, talents, zones, creatures, items |
| 관계 링킹 | quest↔NPC, zone↔dungeon, dungeon↔set | class↔talent, zone↔creature, item↔ego |
| 쿼리 라우터 | 세트/스탯/파밍 감지 | 클래스/스킬/아이템 감지 |
| 시스템 프롬프트 | ESO 전문가 | ToME 전문가 |
| 위키 링크 | `[[Online:Name]]` → en.uesp.net | `[[ToME:Name]]` → te4.org/wiki |
| 추가 데이터 | — | Characters Vault (빌드 통계) |
