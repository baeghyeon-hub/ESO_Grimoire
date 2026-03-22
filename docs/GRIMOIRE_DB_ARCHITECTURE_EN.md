# Grimoire ESO Knowledge Base — System Architecture

> **Last Updated**: 2026-03-22
> **Version**: Phase 3 Complete (Structured DB + Expanded Vector Search)

---

## 1. Overview

Grimoire is an AI chatbot specialized for Elder Scrolls Online (ESO), powered by data crawled from the [UESP](https://en.uesp.net) (Unofficial Elder Scrolls Pages) wiki. Rather than simple keyword search, it delivers comprehensive answers — from game data to deep lore — through a **structured DB + semantic vector search + hybrid RAG pipeline**.

### System Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | Svelte + Tauri | In-game overlay UI |
| Backend | Python (FastAPI + uvicorn) | API server |
| Structured DB | SQLite (FTS5) | Sets / quests / skills / dungeons / NPC data |
| Vector DB | LanceDB (file-based) | Lore embedding vector storage |
| Embedding | Voyage AI (voyage-4) | Text → 1024-dim vectors |
| Reranker | Voyage AI (rerank-2.5) | Search result re-ranking |
| LLM | Multi-provider (Claude, Gemini, GPT, Ollama) | Final answer generation |

---

## 2. Data Source — UESP Wiki

All data is crawled from the [UESP Wiki](https://en.uesp.net) MediaWiki API.

### 2.1 Crawling Scale

| Namespace | Category | Pages | Description |
|-----------|----------|-------|-------------|
| Online (NS=130102) | npcs | 19,759 | NPC information |
| Online | quests | 2,396 | Quest data |
| Online | sets | 747 | Equipment sets |
| Online | skills | 667 | Skills / abilities |
| Online | dungeons | 58 | Dungeons |
| Online | trials | 15 | Trials |
| Online | zones | 49 | Zones |
| Online | companions | 8 | Companions |
| Online | arenas | 7 | Arenas |
| Online | alchemy | 69 | Alchemy reagents |
| Online | achievements | 27 | Achievements |
| Online | antiquities | 4 | Antiquities |
| Online | cp_passive | 44 | CP passives |
| Online | cp_slotted | 73 | CP slottables |
| Online | furnishings | 300 | Furnishings |
| Online | recipes | 18 | Recipes |
| Online | food | 1 | Food |
| Online | delves | 201 | Delves |
| Online | public_dungeons | 39 | Public dungeons |
| Online | factions | — | Factions / guilds |
| Online | crown_store | — | Crown Store |
| Online | mounts | — | Mounts |
| Online | mementos | — | Mementos |
| Online | skill_styles | — | Skill styles |
| Online | classes | — | Classes |
| Online | items | — | Items |
| Online | combat | — | Combat systems |
| Online | armor | — | Armor |
| Online | races | — | Races |
| Online | events | — | Events |
| Online | activities | — | Activities |
| Online | alliance_war | — | Alliance War |
| Lore (NS=130) | lore-books | 3,918 | Lore books |
| Lore | lore-places | 1,283 | Lore places |
| Lore | lore-factions | 595 | Lore factions |
| Lore | lore-creatures | 319 | Lore creatures |
| Lore | lore-gods | 182 | Gods / Daedra |
| Lore | lore-people | 147 | Historical figures |
| Lore | lore-races | 111 | Races |
| Lore | lore-magic | 69 | Magic systems |
| Lore | lore-history | 59 | Historical events |
| Lore | lore-flora | 48 | Flora |
| Lore | lore-appendices | — | Appendices / glossary |
| Lore | lore-disease | — | Diseases |
| Lore | lore-calendar | — | Calendar |
| Lore | lore-names | — | Naming conventions |
| Lore | lore-daedra | — | Daedra |
| Lore | lore-archive | — | Loremaster's Archive |
| Lore | lore-undead | — | Undead |
| Lore | lore-linguistics | — | Linguistics |
| Lore | lore-spells | — | Spells |
| Lore | lore-empires | — | Empires |
| **Total** | | **~33,072** | |

### 2.2 Crawling Method

```
MediaWiki API (api.php)
  ├─ action=query&list=categorymembers  → Page list by category
  ├─ action=parse&prop=wikitext         → Raw wikitext extraction
  └─ Incremental: skip_existing=True    → Skip already-crawled pages
```

- **Rate Limiting**: 0.5s delay between requests
- **Incremental Crawling**: Pages already in the `pages` table are skipped
- **Redirect Handling**: Redirect pages are automatically detected and filtered

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
├── lore_chunks     — 12,114 lore + expanded text chunks
└── lore_chunks_fts — FTS5 lore search index
```

### 3.2 Wikitext Parsing

Transforms UESP wikitext templates into structured data.

**Set parsing example:**
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
→ Stored separately in `sets` + `set_bonuses` tables

**Quest chain parsing:**
```wikitext
{{Online Quest Header
|questgiver=Razum-dar
|prev=The Grip of Madness
|next=To Dune
|prereq=Completion of previous zone quests
}}
```
→ `prev_quest`, `next_quest` fields (1,157 prev / 750 next links)

**Boss strategy extraction:**

Boss strategy text is extracted from dungeon wikitext in 3 stages:
1. `===BossName===` sub-headings under `===Boss Mechanics===` / `===Layout===` sections
2. Content following `'''BossName'''` bold text
3. Fallback: Context surrounding boss name mentions in the body text

→ 102 out of 347 bosses have linked strategy text (29%)

### 3.3 Entity Linking

A linker module that automatically generates cross-references between parsed data.

| Table | Links | Method |
|-------|-------|--------|
| quest_npcs | 2,333 | quest.giver → NPC name matching (exact + partial) |
| zone_dungeons | 73 | dungeon.zone → zone.name matching |
| dungeon_sets | 337 | set.location → dungeon.name reverse matching |

**Alchemy combination matrix:**
- 69 reagents × 4 effects = 32 unique effects
- 257 valid combinations auto-calculated

### 3.4 Query Router (Hybrid Routing)

Analyzes user queries and routes them to one of two modes:

```
User Query
    │
    ├─ "Mother's Sorrow set effects" → STRICT Mode
    │   └─ Direct DB lookup → Inject results into LLM context → Direct answer without tools
    │
    └─ "Recommend a meta build" → CREATIVE Mode
        └─ Grant LLM tool access → LLM autonomously searches and reasons
```

**STRICT Mode** — Triggered by set names, stat keywords, farming locations:
- Pre-fetches set data from DB and injects into the user message
- LLM answers based solely on provided data (hallucination prevention)
- Response speed: Single LLM call, no tool calls needed

**CREATIVE Mode** — Abstract queries (recommendations, comparisons, meta, builds):
- LLM receives 3 tools: `uesp_db`, `uesp_search`, `lore_search`
- LLM autonomously performs necessary searches and synthesizes answers

---

## 4. Phase 2 — Lore Vector Search

A pipeline that makes ESO/TES lore (worldbuilding, history, mythology) semantically searchable.

### 4.1 Pipeline Flow

```
UESP Lore Namespace (NS=130)
         │
    ① Crawling (20 Lore + 22 ESO categories)
         │
    ② Section-based chunking
         │  - Split by == Level 2 == headings
         │  - < 200 tokens: Merge with previous section
         │  - > 1,500 tokens: Split at paragraph boundaries
         │  - Exclude Gallery/See Also/References sections
         │  - Lore-specific wikitext cleanup ({{Lore Link}}, {{Cite Book}}, <ref>, etc.)
         │
    ③ Voyage AI embedding (voyage-4, 1024 dimensions)
         │  - Asymmetric retrieval: document vs. query input types
         │  - Matryoshka embedding: 1024d → 512d reduction possible
         │  - Batch processing: 128 items or 100K tokens per batch
         │
    ④ LanceDB storage (file-based vector DB)
         │
    ⑤ Hybrid search (Vector + BM25 + RRF + Reranker)
         │
    ⑥ LLM answer generation
```

### 4.2 Vector Search Data Scale

| Metric | Value |
|--------|-------|
| Categories | 42 (20 Lore + 22 ESO) |
| Crawled Pages | 33,072 |
| Generated Chunks | 12,114 (after cleanup) |
| Total Tokens | 6,921,607 (~6.9M) |
| Embedding Coverage | 12,114 / 12,114 (100%) |
| LanceDB Vectors | 12,114 (1024-dim, float32) |

### 4.3 Chunking Strategy

```python
# Section-based chunking (pipeline/parsers/lore.py)

LoreChunk(
    page_title="Lore:Molag Bal",
    section="Behavior",
    text="Molag Bal is arrogant, calculating...",
    token_count=423,
)
```

**Why section-based?**
- Fixed-size windows (e.g., 500-token sliding) break context
- Sections = semantic units. "Molag Bal > Behavior" and "Molag Bal > Appearance" are distinct meaning blocks
- Displaying `page_title + section` in results provides clear source attribution

**Merge/split rules:**
- `< 200 tokens` → Merge with previous section (prevent overly short chunks)
- `> 1,500 tokens` → Split at `\n\n` (blank line) boundaries
- Token estimation: `len(text.split()) * 1.3`

### 4.4 Embedding — Voyage AI

| Setting | Value |
|---------|-------|
| Model | voyage-4 |
| Output Dimension | 1024 |
| Input Type | `document` (indexing) / `query` (searching) |
| Batch Size | 128 items or 100K tokens |
| Total Cost | **$0** (200M free tier, used ~7M = 3.5%) |

**Asymmetric Retrieval:**
- Document embedding: `input_type="document"` — Optimized for long text
- Query embedding: `input_type="query"` — Optimized for short questions
- This asymmetric approach improves retrieval accuracy over same-type embedding

### 4.5 Hybrid Search Pipeline

```
User Query: "Why did the Dwemer disappear?"
         │
    Query Expansion (Korean/abbreviations → English: 드웨머 → Dwemer)
         │
    ┌────┴────┐
    │         │
 Vector    BM25 (FTS5)
 Search    Search (expanded query)
    │         │
 Top-30    Top-30
    │         │
    └────┬────┘
         │
    RRF (Reciprocal Rank Fusion, k=60)
         │
    Diversification (max 3 per page)
         │
    Voyage Reranker (rerank-2.5, pool=limit×3)
         │
    Top-5 Results → LLM Context
```

**Reciprocal Rank Fusion (RRF):**
```
score(doc) = Σ 1/(k + rank_i)   where k=60
```
- Rank 3 in vector + Rank 1 in BM25 → `1/63 + 1/61 = 0.0323` (boosted by appearing in both)
- Results found by both methods rank higher than single-source results

**Reranker:**
- Voyage rerank-2.5 re-evaluates query-document pair relevance with a 0–1 score
- Initial search recall + reranker precision = optimal results
- Cost: **$0** (200M free tier)

**Query Expansion (v1.0.2+):**
- Korean → English mapping: 드웨머→Dwemer, 데이드라→Daedric Princes, 몰라그 발→Molag Bal, etc. (30+ entries)
- ESO abbreviation mapping: cp→Champion Points, vdsr→Dreadsail Reef, wb→World Boss, etc.
- Particularly effective for BM25 keyword matching (vector search uses original query as it's meaning-based)

**Result Diversification (v1.0.2+):**
- Keep at most 3 chunks per page_title
- Draws information from diverse sources to improve answer quality

**Chunk Quality Filtering (v1.0.2+):**
- Remove name list pages (e.g., Redguard Names/Arena — 648K characters)
- Remove chunks with >15% wiki markup ratio (table-only content)
- Remove chunks with <30% text ratio (template/pipe-only content)
- Remove Bibliography, Deprecated, and Bugs sections
- Total: 120 noise chunks cleaned (12,234 → 12,114)

**Graceful Degradation:**
- No Voyage API key → BM25 only
- Empty LanceDB → BM25 only
- Reranker failure → Fall back to RRF scores

### 4.6 Search Quality Benchmarks

| Query | #1 Result | Score | Sources |
|-------|-----------|-------|---------|
| Who is Molag Bal and what is the Planemeld? | Lore:Planemeld > Introduction | 0.9141 | vector+bm25 |
| What are the Daedric Princes? | Lore:Daedric Princes > Introduction | 0.9492 | vector+bm25 |
| dwemer disappearance | Lore:Dwemer > History (part 2) | 0.9062 | vector+bm25 |
| 아카토쉬는 누구야? (Korean) | Lore:Akatosh > Introduction | 0.8438 | vector |

- Korean queries accurately match English lore pages via vector search
- Hybrid (vector+bm25) results score higher than single-source results

---

## 5. LLM Integration — Answer Generation

### 5.1 Tool Architecture

Three tools are provided to the LLM:

```
┌─────────────────────────────────────────┐
│              LLM (ChatAgent)            │
│                                         │
│  Tool 1: uesp_db                        │
│    → Direct SQLite queries              │
│    → get_set, search_sets, filter_sets  │
│    → get_quest_chain, get_dungeon       │
│    → search_alchemy_combo               │
│                                         │
│  Tool 2: uesp_search                    │
│    → Live UESP Wiki search              │
│    → Via Cloudflare Worker proxy         │
│                                         │
│  Tool 3: lore_search                    │
│    → Hybrid vector + BM25 search        │
│    → Voyage Reranker                    │
│    → Dedicated to lore/history/myth     │
└─────────────────────────────────────────┘
```

### 5.2 Answer Flow Example

**Query:** "Cite lore book passages about why the Dwemer disappeared, and explain in detail how it affects ESO factions"

```
1. Query Router: is_lore=True → CREATIVE mode
2. LLM decides: lore_search("dwemer disappearance theories")
3. Hybrid Search:
   - Vector: Lore:Dwemer > History, Lore:Battle of Red Mountain, ...
   - BM25: "dwemer" + "disappearance" keyword matching
   - RRF merge → Reranker → Top 5
4. LLM decides: lore_search("Tribunal ascension Heart of Lorkhan")
5. Additional context retrieved
6. LLM synthesizes:
   - 3 hypotheses (Divine Punishment, Ascension, Dragon Break)
   - Direct lore book quotes ("Our sacred engineering...")
   - Impact analysis across ESO's 3 factions + comparison table
   - UESP wiki links ([[Lore:Dwemer]], [[Online:Tribunal]])
```

### 5.3 Response Formatting

- **UESP Links**: `[[Online:Name]]`, `[[Lore:Name]]` format for wiki page references
- **Image Embedding**: `[IMG:thumb|full|caption]` format
- **Structure**: Markdown headings, tables, bullet lists
- **Length Control**: Token limit-based — 4K (brief) to 32K (maximum detail) in 4 tiers
- **Multilingual**: Auto-detects user language → responds in the same language

---

## 6. Technical Stack Details

### 6.1 File Structure

```
Grimoire/
├── core/
│   ├── agent.py          — ChatAgent (LLM conversation engine)
│   ├── config.py         — Configuration management (multi-provider)
│   ├── providers.py      — LLM provider abstraction
│   ├── tools.py          — Tool definitions (uesp_db, uesp_search, lore_search)
│   └── uesp_agent.py     — Orchestrator (routing + conversation)
├── pipeline/
│   ├── crawler.py        — UESP MediaWiki crawler
│   ├── parser.py         — Wikitext → structured data conversion
│   ├── parsers/
│   │   ├── sets.py       — Set parser
│   │   ├── quests.py     — Quest parser
│   │   ├── skills.py     — Skill parser
│   │   ├── dungeons.py   — Dungeon / boss parser
│   │   ├── zones.py      — Zone parser
│   │   └── lore.py       — Lore chunking parser
│   ├── indexer.py        — Crawl → parse → DB storage
│   ├── linker.py         — Entity relationship linking
│   ├── db.py             — SQLite schema + CRUD
│   ├── lore_chunker.py   — Lore page → chunk conversion
│   ├── embedder.py       — Voyage AI embedding
│   ├── vector_store.py   — LanceDB vector store
│   ├── lore_search.py    — Hybrid search engine (query expansion + diversification)
│   ├── chunk_cleanup.py  — Chunk quality cleanup (noise removal)
│   ├── build_lore.py     — Lore pipeline master script
│   └── build_expanded.py — Expanded category pipeline
├── rag/
│   └── query_router.py   — Query classification (Strict / Creative)
├── db/
│   ├── uesp.db           — SQLite DB (structured data)
│   └── lore.lance/       — LanceDB (vector data)
└── docs/
    ├── GRIMOIRE_DB_ARCHITECTURE.md     ← Korean version
    └── GRIMOIRE_DB_ARCHITECTURE_EN.md  ← This document
```

### 6.2 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| lancedb | ≥0.6.0 | File-based vector database |
| pyarrow | ≥14.0.0 | LanceDB data format |
| voyageai | ≥0.3.0 | Embedding + Reranking API |
| sqlite3 | (built-in) | Structured data storage |

### 6.3 PyInstaller Compatibility

- LanceDB: No server required, file-based → deployable as exe
- SQLite: Python built-in module
- Voyage API: HTTP calls only → no external dependencies
- `sys.frozen` detection for automatic path switching in deployed environments

---

## 7. Cost Analysis

| Component | Provider | Cost |
|-----------|----------|------|
| Embedding (voyage-4) | Voyage AI | **$0** (Free tier: 200M tokens, used ~7M = 3.5%) |
| Reranking (rerank-2.5) | Voyage AI | **$0** (Free tier: 200M tokens) |
| LLM (answer generation) | User's choice | User's own API key (Claude/Gemini/GPT/Ollama) |
| Vector DB (LanceDB) | Self-hosted | **$0** (file-based, no server) |
| Data Source (UESP) | Public API | **$0** (free wiki) |
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
│ Text Chunks            :    12,114  │
│ Embedded Vectors       :    12,114  │
│ Total Tokens           : 6,921,607  │
│ Vector Dimensions      :     1,024  │
│ Embedding Model        : voyage-4   │
│ Categories             :        42  │
│ Search Methods         : 3 (hybrid) │
│ Infrastructure Cost    :        $0  │
└─────────────────────────────────────┘
```
