# Grimoire ESO Knowledge Base — System Architecture

> **Last Updated**: 2026-03-22
> **Version**: Phase 3 Complete (Structured DB + Expanded Vector Search)

---

## 1. Overview

Grimoire는 Elder Scrolls Online(ESO) 전문 AI 챗봇으로, UESP(Unofficial Elder Scrolls Pages) 위키에서 크롤링한 데이터를 기반으로 동작한다. 단순 키워드 검색이 아닌 **구조화된 DB + 시맨틱 벡터 검색 + 하이브리드 RAG 파이프라인**을 통해 게임 데이터부터 깊은 Lore 질문까지 포괄적으로 답변한다.

### System Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | Svelte + Tauri | 게임 오버레이 UI |
| Backend | Python (FastAPI + uvicorn) | API 서버 |
| Structured DB | SQLite (FTS5) | 세트/퀘스트/스킬/던전/NPC 데이터 |
| Vector DB | LanceDB (file-based) | Lore 임베딩 벡터 저장 |
| Embedding | Voyage AI (voyage-4) | 텍스트 → 1024차원 벡터 |
| Reranker | Voyage AI (rerank-2.5) | 검색 결과 재정렬 |
| LLM | Multi-provider (Claude, Gemini, GPT, Ollama) | 최종 답변 생성 |

---

## 2. Data Source — UESP Wiki

모든 데이터는 [UESP Wiki](https://en.uesp.net)의 MediaWiki API에서 크롤링한다.

### 2.1 크롤링 규모

| Namespace | Category | Pages | Description |
|-----------|----------|-------|-------------|
| Online (NS=130102) | npcs | 19,759 | NPC 정보 |
| Online | quests | 2,396 | 퀘스트 데이터 |
| Online | sets | 747 | 장비 세트 |
| Online | skills | 667 | 스킬/능력 |
| Online | dungeons | 58 | 던전 |
| Online | trials | 15 | 트라이얼 |
| Online | zones | 49 | 지역 |
| Online | companions | 8 | 컴패니언 |
| Online | arenas | 7 | 아레나 |
| Online | alchemy | 69 | 연금술 재료 |
| Online | achievements | 27 | 업적 |
| Online | antiquities | 4 | 고대유물 |
| Online | cp_passive | 44 | CP 패시브 |
| Online | cp_slotted | 73 | CP 슬롯 |
| Online | furnishings | 300 | 가구 |
| Online | recipes | 18 | 레시피 |
| Online | food | 1 | 음식 |
| Online | delves | 201 | 델브 |
| Online | public_dungeons | 39 | 공개 던전 |
| Online | factions | — | 팩션/길드 |
| Online | crown_store | — | 크라운 상점 |
| Online | mounts | — | 탈것 |
| Online | mementos | — | 메멘토 |
| Online | skill_styles | — | 스킬 스타일 |
| Online | classes | — | 클래스 |
| Online | items | — | 아이템 |
| Online | combat | — | 전투 시스템 |
| Online | armor | — | 방어구 |
| Online | races | — | 종족 |
| Online | events | — | 이벤트 |
| Online | activities | — | 활동 |
| Online | alliance_war | — | 얼라이언스 워 |
| Lore (NS=130) | lore-books | 3,918 | 로어 서적 |
| Lore | lore-places | 1,283 | 로어 장소 |
| Lore | lore-factions | 595 | 로어 팩션 |
| Lore | lore-creatures | 319 | 로어 생물 |
| Lore | lore-gods | 182 | 신/데이드라 |
| Lore | lore-people | 147 | 역사적 인물 |
| Lore | lore-races | 111 | 종족 |
| Lore | lore-magic | 69 | 마법 체계 |
| Lore | lore-history | 59 | 역사적 사건 |
| Lore | lore-flora | 48 | 식물 |
| Lore | lore-appendices | — | 부록/용어 |
| Lore | lore-disease | — | 질병 |
| Lore | lore-calendar | — | 달력 |
| Lore | lore-names | — | 이름 체계 |
| Lore | lore-daedra | — | 데이드라 |
| Lore | lore-archive | — | 로어마스터 아카이브 |
| Lore | lore-undead | — | 언데드 |
| Lore | lore-linguistics | — | 언어학 |
| Lore | lore-spells | — | 주문 |
| Lore | lore-empires | — | 제국 |
| **Total** | | **~33,072** | |

### 2.2 크롤링 방식

```
MediaWiki API (api.php)
  ├─ action=query&list=categorymembers  → 카테고리별 페이지 목록
  ├─ action=parse&prop=wikitext         → 원본 wikitext 취득
  └─ Incremental: skip_existing=True    → 기존 페이지 스킵
```

- **Rate Limiting**: 요청 간 0.5초 딜레이
- **Incremental Crawling**: `pages` 테이블에 이미 있는 페이지는 스킵
- **Redirect 처리**: redirect 페이지 자동 감지 및 필터링

---

## 3. Phase 1 — Structured Database

### 3.1 Schema Overview

```
uesp.db (SQLite)
├── pages           — 33,072 raw wikitext pages
├── sets            — 720 equipment sets
├── set_bonuses     — 2,503 set bonus entries
├── quests          — 2,383 quests (with prev/next chain)
├── skills          — 650 skills
├── dungeons        — 74 dungeons (group + solo)
├── dungeon_bosses  — 347 bosses (102 with strategy text)
├── zones           — 48 zones
├── npcs            — 21,165 NPCs
├── quest_npcs      — 2,333 quest↔NPC links
├── zone_dungeons   — 73 zone↔dungeon links
├── dungeon_sets    — 337 dungeon↔set links
├── pages_fts       — FTS5 full-text search index
├── lore_chunks     — 12,234 lore + expanded text chunks
└── lore_chunks_fts — FTS5 lore search index
```

### 3.2 Wikitext Parsing

UESP의 wikitext 템플릿을 구조화된 데이터로 변환한다.

**세트 파싱 예시:**
```wikitext
{{Online Set Summary
|setname=Mother's Sorrow
|type=Overland
|armor=Light
|location=Deshaan
|bonus1=(2 items) Adds 1096 Maximum Magicka
|bonus5=(5 items) Adds 2629 Critical Chance
}}
```
→ `sets` 테이블 + `set_bonuses` 테이블로 분리 저장

**퀘스트 체인 파싱:**
```wikitext
{{Online Quest Header
|questgiver=Razum-dar
|prev=The Grip of Madness
|next=To Dune
|prereq=Completion of previous zone quests
}}
```
→ `prev_quest`, `next_quest` 필드 (1,157개 prev / 750개 next 연결)

**보스 전략 추출:**

던전 wikitext에서 보스별 전략 텍스트를 3단계로 추출:
1. `===Boss Mechanics===` / `===Layout===` 섹션의 `===BossName===` 서브 헤딩
2. `'''BossName'''` 볼드 텍스트 이후 콘텐츠
3. Fallback: 본문에서 보스 이름 주변 문맥 추출

→ 347개 보스 중 102개에 전략 텍스트 연결 (29%)

### 3.3 Entity Linking (관계 테이블)

파싱된 데이터 간 교차 참조를 자동 생성하는 링커 모듈.

| Table | Links | Method |
|-------|-------|--------|
| quest_npcs | 2,333 | quest.giver → NPC name 매칭 (exact + partial) |
| zone_dungeons | 73 | dungeon.zone → zone.name 매칭 |
| dungeon_sets | 337 | set.location → dungeon.name 역매칭 |

**연금술 조합 매트릭스:**
- 69개 재료 × 4개 효과 = 32개 고유 효과
- 257개 유효 조합 자동 계산

### 3.4 Query Router (Hybrid Routing)

사용자 질의를 분석하여 두 가지 모드로 분기:

```
User Query
    │
    ├─ "Mother's Sorrow 세트 효과" → STRICT Mode
    │   └─ DB 직접 조회 → 결과를 LLM 컨텍스트에 주입 → Tool 없이 직답
    │
    └─ "메타 빌드 추천해줘" → CREATIVE Mode
        └─ LLM에게 Tool 권한 부여 → LLM이 자율적으로 검색/판단
```

**STRICT Mode** — 세트 이름, 스탯 키워드, 파밍 위치 감지 시:
- DB에서 세트 정보를 미리 조회하여 사용자 메시지에 주입
- LLM은 주어진 데이터만으로 답변 (환각 방지)
- 응답 속도: Tool call 없이 1회 LLM 호출로 완료

**CREATIVE Mode** — 추상적 질의 (추천, 비교, 메타, 빌드):
- LLM에게 3개 Tool 제공: `uesp_db`, `uesp_search`, `lore_search`
- LLM이 자율적으로 필요한 검색 수행 후 종합 답변

---

## 4. Phase 2 — Lore Vector Search

ESO/TES의 Lore(세계관, 역사, 신화) 데이터를 시맨틱 검색 가능하게 만드는 파이프라인.

### 4.1 파이프라인 흐름

```
UESP Lore Namespace (NS=130)
         │
    ① 크롤링 (20개 Lore + 22개 ESO 카테고리)
         │
    ② 섹션 기반 청킹
         │  - == Level 2 == 헤딩으로 분할
         │  - 200 토큰 미만: 이전 섹션에 병합
         │  - 1,500 토큰 초과: 문단 경계에서 분할
         │  - Gallery/See Also/References 섹션 제외
         │  - Lore-specific wikitext 정제 ({{Lore Link}}, {{Cite Book}}, <ref> 등)
         │
    ③ Voyage AI 임베딩 (voyage-4, 1024차원)
         │  - Asymmetric retrieval: document용 / query용 분리
         │  - Matryoshka embedding: 1024d → 512d 축소
         │  - 배치 처리: 128개 or 100K 토큰 단위
         │
    ④ LanceDB 저장 (파일 기반 벡터 DB)
         │
    ⑤ 하이브리드 검색 (Vector + BM25 + RRF + Reranker)
         │
    ⑥ LLM 답변 생성
```

### 4.2 벡터 검색 데이터 규모

| Metric | Value |
|--------|-------|
| 카테고리 | 42개 (Lore 20 + ESO 22) |
| 크롤링 페이지 | 33,072 |
| 생성된 청크 | 12,234 |
| 총 토큰 수 | 6,921,607 (약 692만) |
| 임베딩 완료 | 12,234 / 12,234 (100%) |
| LanceDB 벡터 | 12,234개 (1024차원, float32) |

### 4.3 Chunking Strategy

```python
# 섹션 기반 청킹 (pipeline/parsers/lore.py)

LoreChunk(
    page_title="Lore:Molag Bal",
    section="Behavior",
    text="Molag Bal is arrogant, calculating...",
    token_count=423,
)
```

**왜 섹션 기반인가?**
- 고정 크기 윈도우 (예: 500토큰 슬라이딩)는 문맥을 끊음
- 섹션 = 의미 단위. "Molag Bal > Behavior"와 "Molag Bal > Appearance"는 별개의 의미 블록
- 검색 결과에 `page_title + section`을 표시하여 출처를 명확히 제공

**병합/분할 규칙:**
- `< 200 tokens` → 이전 섹션에 병합 (너무 짧은 청크 방지)
- `> 1,500 tokens` → `\n\n` (빈 줄) 기준으로 분할
- 토큰 추정: `len(text.split()) * 1.3`

### 4.4 Embedding — Voyage AI

| Setting | Value |
|---------|-------|
| Model | voyage-4 |
| Output Dimension | 1024 |
| Input Type | `document` (저장 시) / `query` (검색 시) |
| Batch Size | 128 items or 100K tokens |
| Total Cost | **$0** (200M free tier, 사용량 ~5M = 2.5%) |

**Asymmetric Retrieval:**
- 문서 임베딩: `input_type="document"` — 긴 텍스트 최적화
- 쿼리 임베딩: `input_type="query"` — 짧은 질문 최적화
- 이 비대칭 방식이 동일 타입 대비 검색 정확도 향상

### 4.5 Hybrid Search Pipeline

```
User Query: "드웨머가 왜 사라졌어?"
         │
    ┌────┴────┐
    │         │
 Vector    BM25 (FTS5)
 Search    Search
    │         │
 Top-20    Top-20
    │         │
    └────┬────┘
         │
    RRF (Reciprocal Rank Fusion, k=60)
         │
    Merged & Sorted
         │
    Voyage Reranker (rerank-2.5)
         │
    Top-5 Results → LLM Context
```

**Reciprocal Rank Fusion (RRF):**
```
score(doc) = Σ 1/(k + rank_i)   where k=60
```
- 벡터 검색에서 3위 + BM25에서 1위 → `1/63 + 1/61 = 0.0323` (양쪽 합산으로 상위 랭크)
- 한쪽에서만 나온 결과보다 양쪽 모두에서 나온 결과가 우선

**Reranker:**
- Voyage rerank-2.5 모델이 쿼리-문서 쌍의 관련성을 0~1 점수로 재평가
- 초기 검색의 recall + reranker의 precision = 최적 결과
- Cost: **$0** (200M free tier)

**Graceful Degradation:**
- Voyage API 키 없음 → BM25만 사용
- LanceDB 비어있음 → BM25만 사용
- Reranker 실패 → RRF 점수 기반 반환

### 4.6 검색 품질 벤치마크

| Query | #1 Result | Score | Sources |
|-------|-----------|-------|---------|
| Who is Molag Bal and what is the Planemeld? | Lore:Planemeld > Introduction | 0.9141 | vector+bm25 |
| What are the Daedric Princes? | Lore:Daedric Princes > Introduction | 0.9492 | vector+bm25 |
| dwemer disappearance | Lore:Dwemer > History (part 2) | 0.9062 | vector+bm25 |
| 아카토쉬는 누구야? (Korean) | Lore:Akatosh > Introduction | 0.8438 | vector |

- 한국어 질문도 벡터 검색으로 정확한 영어 Lore 페이지 매칭
- 하이브리드(vector+bm25) 결과가 단일 소스보다 높은 점수

---

## 5. LLM Integration — Answer Generation

### 5.1 Tool Architecture

LLM에게 3개의 도구를 제공:

```
┌─────────────────────────────────────────┐
│              LLM (ChatAgent)            │
│                                         │
│  Tool 1: uesp_db                        │
│    → SQLite 직접 조회                    │
│    → get_set, search_sets, filter_sets  │
│    → get_quest_chain, get_dungeon       │
│    → search_alchemy_combo               │
│                                         │
│  Tool 2: uesp_search                    │
│    → UESP Wiki 실시간 검색              │
│    → Cloudflare Worker 프록시 경유       │
│                                         │
│  Tool 3: lore_search                    │
│    → 하이브리드 벡터 + BM25 검색         │
│    → Voyage Reranker                    │
│    → Lore/역사/신화 질문 전용            │
└─────────────────────────────────────────┘
```

### 5.2 Answer Flow Example

**질의:** "드웨머가 사라진 이유에 대한 로어북 구절을 인용하며, ESO 팩션에 어떤 영향을 주는지 상세하게 알려줘"

```
1. Query Router: is_lore=True → CREATIVE mode
2. LLM decides: lore_search("dwemer disappearance theories")
3. Hybrid Search:
   - Vector: Lore:Dwemer > History, Lore:Battle of Red Mountain, ...
   - BM25: "dwemer" + "disappearance" 키워드 매칭
   - RRF merge → Reranker → Top 5
4. LLM decides: lore_search("Tribunal ascension Heart of Lorkhan")
5. Additional context retrieved
6. LLM synthesizes:
   - 3가지 가설 (신벌설, 승천설, 드래곤 브레이크)
   - 로어북 직접 인용 ("우리의 신성한 공학은...")
   - ESO 3개 팩션별 영향 분석 + 비교 테이블
   - UESP 위키 링크 ([[Lore:Dwemer]], [[Online:Tribunal]])
```

### 5.3 Response Formatting

- **UESP 링크**: `[[Online:Name]]`, `[[Lore:Name]]` 형식으로 위키 페이지 참조
- **이미지 삽입**: `[IMG:thumb|full|caption]` 형식
- **구조화**: Markdown 헤딩, 테이블, 불릿 리스트
- **토큰 제한 기반 길이 조절**: 4K (짧은 답변) ~ 32K (최대 상세) 4단계
- **다국어**: 사용자 언어 자동 감지 → 동일 언어로 답변

---

## 6. Technical Stack Details

### 6.1 File Structure

```
Grimoire/
├── core/
│   ├── agent.py          — ChatAgent (LLM 대화 엔진)
│   ├── config.py         — 설정 관리 (multi-provider)
│   ├── providers.py      — LLM 프로바이더 추상화
│   ├── tools.py          — Tool 함수 정의 (uesp_db, uesp_search, lore_search)
│   └── uesp_agent.py     — 오케스트레이터 (라우팅 + 대화)
├── pipeline/
│   ├── crawler.py        — UESP MediaWiki 크롤러
│   ├── parser.py         — Wikitext → 구조화 데이터 변환
│   ├── parsers/
│   │   ├── sets.py       — 세트 파서
│   │   ├── quests.py     — 퀘스트 파서
│   │   ├── skills.py     — 스킬 파서
│   │   ├── dungeons.py   — 던전/보스 파서
│   │   ├── zones.py      — 지역 파서
│   │   └── lore.py       — Lore 청킹 파서
│   ├── indexer.py        — 크롤링 → 파싱 → DB 저장
│   ├── linker.py         — 엔티티 관계 링킹
│   ├── db.py             — SQLite 스키마 + CRUD
│   ├── lore_chunker.py   — Lore 페이지 → 청크 변환
│   ├── embedder.py       — Voyage AI 임베딩
│   ├── vector_store.py   — LanceDB 벡터 저장소
│   ├── lore_search.py    — 하이브리드 검색 엔진
│   └── build_lore.py     — Lore 파이프라인 마스터 스크립트
├── rag/
│   └── query_router.py   — 질의 분류 (Strict/Creative)
├── db/
│   ├── uesp.db           — SQLite DB (구조화 데이터)
│   └── lore.lance/       — LanceDB (벡터 데이터)
└── docs/
    └── GRIMOIRE_DB_ARCHITECTURE.md  ← 이 문서
```

### 6.2 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| lancedb | ≥0.6.0 | File-based vector database |
| pyarrow | ≥14.0.0 | LanceDB 데이터 포맷 |
| voyageai | ≥0.3.0 | Embedding + Reranking API |
| sqlite3 | (built-in) | Structured data storage |

### 6.3 PyInstaller Compatibility

- LanceDB: 서버 불필요, 파일 기반 → exe 배포 가능
- SQLite: Python 내장 모듈
- Voyage API: HTTP 호출만 → 외부 의존성 없음
- `sys.frozen` 감지로 배포 환경 경로 자동 전환

---

## 7. Cost Analysis

| Component | Provider | Cost |
|-----------|----------|------|
| Embedding (voyage-4) | Voyage AI | **$0** (Free tier: 200M tokens, used ~7M = 3.5%) |
| Reranking (rerank-2.5) | Voyage AI | **$0** (Free tier: 200M tokens) |
| LLM (답변 생성) | User's choice | 사용자 API 키 (Claude/Gemini/GPT/Ollama) |
| Vector DB (LanceDB) | Self-hosted | **$0** (파일 기반, 서버 불필요) |
| Data Source (UESP) | Public API | **$0** (무료 위키) |
| **Total Infrastructure** | | **$0** |

---

## 8. Summary Statistics

```
┌─────────────────────────────────────┐
│       Grimoire Knowledge Base       │
├─────────────────────────────────────┤
│ Total Crawled Pages    :    33,072  │
│ Structured Records     :    10,552  │
│ NPCs                   :    21,165  │
│ Entity Relationships   :     2,743  │
│ Text Chunks            :    12,234  │
│ Embedded Vectors       :    12,234  │
│ Total Tokens           : 6,921,607  │
│ Vector Dimensions      :     1,024  │
│ Embedding Model        : voyage-4   │
│ Categories             :        42  │
│ Search Methods         : 3 (hybrid) │
│ Infrastructure Cost    :        $0  │
└─────────────────────────────────────┘
```
