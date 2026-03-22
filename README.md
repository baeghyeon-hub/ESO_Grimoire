# Grimoire

An AI-powered Elder Scrolls Online companion that runs as an in-game overlay. Ask anything about ESO — from set bonuses and quest guides to deep lore about the Daedric Princes.

![Grimoire Mini Bar](screenshots/mini_bar.gif)

## Features

### Always-On Overlay
Grimoire lives on top of your game as a compact, draggable mini bar. Click to expand the full chat panel — no alt-tabbing required.

![Welcome Screen](screenshots/center.png)

### Multi-Provider AI
Choose your preferred LLM provider. Bring your own API key and switch freely between models.

<p align="center">
  <img src="screenshots/setting_1.png" width="320" alt="Provider Selection" />
  &nbsp;&nbsp;
  <img src="screenshots/setting_2.png" width="320" alt="Model & Response Settings" />
</p>

**Supported Providers:**
| Provider | Models |
|----------|--------|
| Anthropic | Claude Haiku 4.5, Sonnet 4 |
| Google | Gemini 2.0 Flash, 2.5 Flash, 3 Flash |
| OpenAI | GPT-4o, GPT-4o Mini, GPT-4.1 Mini, GPT-4.1 Nano |
| Ollama | Any local model (Qwen3, Gemma3, Llama, etc.) |

### Deep Lore Knowledge

Ask complex lore questions and get comprehensive, structured answers with collapsible sections, inline UESP references, and comparison tables — all sourced from a local database of **33,000+ UESP wiki pages**.

> *"Tell me about Lorkhan"*

![Lore Response 1](screenshots/1.png)
![Lore Response 2](screenshots/2.png)
![Lore Response 3](screenshots/3.png)
![Lore Response 4](screenshots/4.png)
![Lore Response 5](screenshots/5.png)

### Integrated Image Viewer

In-line images open in a dedicated side-car viewer with zoom, pan, and source details.

![Image Viewer](screenshots/6.png)

### Quick Lookup

Select any highlighted term (item, place, NPC) to instantly ask Grimoire or jump to the UESP wiki page.

![Selection UI](screenshots/selection%20ui.png)

---

## How It Works

Grimoire combines a **structured SQLite database** with **semantic vector search** to give the AI accurate, grounded answers instead of hallucinations.

### Data Pipeline

```
UESP Wiki (33,072 pages)
    │
    ├─ Structured Parsing ──→ SQLite DB
    │   Sets, Quests, Skills, Dungeons,
    │   NPCs, Zones, Boss Strategies,
    │   Alchemy Combos, Quest Chains
    │
    └─ Lore + Expanded ──→ Vector Search
        12,114 chunks across 42 categories
        Voyage AI embeddings (voyage-4, 1024d)
        Hybrid: Vector + BM25 + Reranker
```

### Query Routing

| Query Type | Mode | How It Works |
|-----------|------|-------------|
| *"Mother's Sorrow set"* | **Strict** | Direct DB lookup → deterministic answer |
| *"Best magicka build?"* | **Creative** | LLM autonomously searches DB + wiki |
| *"Why did the Dwemer disappear?"* | **Lore** | Hybrid vector search → sourced narrative |

### Database Stats

| Category | Count |
|----------|-------|
| Total Crawled Pages | 33,072 |
| Structured Records | 10,552 |
| Equipment Sets | 720 |
| Quests (with chains) | 2,383 |
| Skills | 650 |
| Dungeon Bosses | 347 |
| NPCs | 21,165 |
| Lore + Expanded Chunks | 12,114 |
| Embedded Vectors (voyage-4, 1024d) | 12,114 |
| Total Tokens Embedded | 6,921,607 |
| Entity Relationships | 2,743 |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop App | [Tauri](https://tauri.app) + Svelte |
| Backend | Python, FastAPI |
| Structured DB | SQLite with FTS5 |
| Vector DB | LanceDB (file-based, no server) |
| Embeddings | Voyage AI (voyage-4) |
| Reranker | Voyage AI (rerank-2.5) |
| Data Source | [UESP Wiki](https://en.uesp.net) MediaWiki API |

## Getting Started

### Option A: Download Release (Recommended)

1. Download **`Grimoire_1.0.1_x64-setup.exe`** from the [Releases](https://github.com/baeghyeon-hub/ESO_Grimoire/releases) page
2. Run the installer — installs to `%LOCALAPPDATA%\Grimoire` (no admin required)
3. Download **`grimoire-db.zip`** from [v1.0.2](https://github.com/baeghyeon-hub/ESO_Grimoire/releases/tag/v1.0.2)
4. Extract the zip so the folder structure looks like this:
   ```
   %LOCALAPPDATA%\Grimoire\
   └── db\
       ├── uesp.db
       └── lore.lance\
   ```
   > **Tip:** Press `Win + R`, type `%LOCALAPPDATA%\Grimoire` and hit Enter to open the install folder. Create a `db` folder there and extract the zip contents into it.
5. Launch Grimoire — if the DB is missing, a dialog will guide you
6. Open **Settings** (gear icon), select your AI provider and enter your API key

### Option B: Build from Source

**Prerequisites:** Python 3.10+, Node.js 18+, Rust

```bash
# Clone the repository
git clone https://github.com/baeghyeon-hub/ESO_Grimoire.git
cd ESO_Grimoire

# Install dependencies
pip install -r requirements.txt
npm install

# Copy and configure settings
cp config.example.json config.json
# Edit config.json — add your API key

# Build the ESO database (first time, ~1 hour)
python -m pipeline.crawler
python -m pipeline.indexer
python -m pipeline.linker
python -m pipeline.build_lore

# Run in development mode
npm run dev

# Or build the full installer
npm run build:all
```

## License

MIT
