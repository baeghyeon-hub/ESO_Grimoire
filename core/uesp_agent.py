"""
UESP agent orchestrator.

System prompt, singleton management, chat() entry point.
Conversation engine in agent.py, tool implementations in tools.py.
"""
from __future__ import annotations

import logging
import threading

from core.agent import ChatAgent, Conversation
from core.providers import create_provider
from core.tools import make_search_fn, make_db_fn, make_lore_search_fn

_LOG = logging.getLogger(__name__)

# ── System Prompts ────────────────────────────────────────

_COMMON_PROMPT = (
    "Response format:\n"
    "- Use English proper nouns for ESO terms.\n"
    "- Wrap ESO/TES proper nouns in double brackets with UESP namespace prefix.\n"
    "  * Online: for ESO gameplay content (items, sets, dungeons, trials, NPCs, quests, zones, skills, factions): "
    "[[Online:Sentinel]], [[Online:Mother's Sorrow]], [[Online:Ruins of Mazzatun]], [[Online:Aldmeri Dominion]].\n"
    "  * Lore: for lore/history topics (gods, Daedra, races, historical figures, dynasties, events, planes, concepts): "
    "[[Lore:Aedra]], [[Lore:Kynareth]], [[Lore:Reman Dynasty]], [[Lore:Khajiit]], [[Lore:Interregnum]], [[Lore:Empire]].\n"
    "- ALWAYS include Online: or Lore: prefix. Never write bare [[Name]] without prefix.\n"
    "- Use pipe syntax for display text: [[Lore:The Thief (constellation)|Thief]], "
    "[[Online:The Warrior (constellation)|Warrior]]. The text after | is what the user sees.\n"
    "- Only link actual UESP wiki page names that exist. Do NOT link common English words "
    "(e.g., Critical, Damage, Health, Stamina, Magicka, Light, Heavy, etc.) — these are NOT wiki pages.\n"
    "- CRITICAL SOURCE RULE: NEVER invent or fabricate wiki page names, lore book titles, or source names. "
    "When citing lore sources, ONLY use page titles that appear in [Source: ...] headers from lore_search results. "
    "If a book or page was NOT in your search results, do NOT link it with [[Lore:...]] or [[Online:...]]. "
    "Prefer using bold **Book Title** for titles you recall but did not search, instead of [[]] links. "
    "Wrong: [[Lore:The High King's Decree]] (invented). Right: **The High King's Decree** (unverified mention).\n"
    "- Use [[]] for proper nouns, use **bold** only for emphasis on common words.\n"
    "- Include set bonuses with exact numbers.\n"
    "- Structure long answers with ## or ### Markdown headings to organize sections.\n\n"
    "CRITICAL formatting rules — ALWAYS follow these:\n"
    "- When listing multiple skills, abilities, or mechanics: use ### heading for EACH one, "
    "followed by its description in a separate paragraph. Example:\n"
    "  ### Chain Lightning\n"
    "  Description here as its own paragraph.\n"
    "  ### Conjured Axe\n"
    "  Description here as its own paragraph.\n"
    "- NEVER write multiple abilities in one continuous paragraph. This is the #1 formatting mistake to avoid.\n"
    "- When comparing items or listing stats, use Markdown tables with | columns |.\n"
    "- Use bullet points (- ) for short tips or facts.\n"
    "- Use numbered lists (1. ) only for sequential steps or priority rankings.\n"
    "- Keep each paragraph under 3-4 sentences max."
)

# Length hints based on token setting
_LENGTH_HINTS = {
    4096: (
        "IMPORTANT — SHORT ANSWER MODE: Keep your response under 150 words. "
        "Give only the essential facts in 2-3 short paragraphs. No headings, no sections. "
        "Skip background/history/lore details. Just answer the question directly."
    ),
    8192: (
        "STANDARD ANSWER MODE: Aim for 200-400 words. "
        "Give a clear, well-organized answer. Use 1-2 headings if needed. "
        "Include key details but don't over-explain."
    ),
    16384: (
        "DETAILED ANSWER MODE: Aim for 500-800 words. "
        "Give a comprehensive answer with multiple ## sections. "
        "Explain mechanics in depth, include related tips, strategy advice, comparisons, "
        "and relevant context. Cover the topic thoroughly. "
        "Use multiple tool searches with different keywords to gather enough data before answering."
    ),
    32768: (
        "MAXIMUM DETAIL MODE. Your response MUST be at least 800 words — "
        "responses under 600 words are NOT acceptable in this mode. "
        "Prioritize DEPTH over breadth. Don't create many shallow sections — "
        "write fewer sections but with rich, detailed paragraphs (5+ sentences each). "
        "For EVERY claim, include specific numbers, names, or examples. "
        "Search strategy: make 2-4 separate tool calls with different search terms "
        "to gather comprehensive data before writing your answer. "
        "After writing, mentally check: is each section at least 3-4 sentences? "
        "If not, expand it with practical details, comparisons, or related info. "
        "Combine tool results with your own ESO knowledge to fill gaps."
    ),
}

SYSTEM_PROMPT = (
    "ESO expert assistant with three tools:\n"
    "1) uesp_db — fast local DB with structured set data (bonuses, type, location). Try this FIRST for set queries.\n"
    "2) uesp_search — searches UESP wiki for anything (skills, dungeons, quests, mechanics, etc.).\n"
    "3) lore_search — semantic search over TES lore (history, gods, Daedra, races, people, events, places, magic). "
    "Use for narrative/lore questions about Elder Scrolls universe. "
    "Results include [Source: Lore:PageTitle > Section] headers — ONLY cite these exact titles as sources.\n\n"
    + _COMMON_PROMPT + "\n\n"
    "Search strategy:\n"
    "- For set info (bonuses, type, location): use uesp_db first (get_set or search_sets).\n"
    "- For filtering (e.g. 'light armor trial sets'): use uesp_db filter_sets.\n"
    "- For lore/history/narrative questions (gods, Daedra, races, historical events, mythology): use lore_search.\n"
    "- For non-set gameplay info or if DB has no result: use uesp_search.\n"
    "- Always use English names for tool queries (e.g., vDSR→Dreadsail Reef).\n"
    "Combine tool data with your ESO knowledge for practical answers.\n\n"
    "Images: results may have IMAGES section (thumb|full|caption format).\n"
    "Embed with [IMG:thumb_url|full_url|caption]. Include 1-2 relevant images."
)

STRICT_PROMPT = (
    "ESO expert assistant. Answer ONLY based on the DB data provided in the user message. "
    "Do NOT attempt to call any tools or functions.\n\n"
    + _COMMON_PROMPT
)


# ── Singleton Management ────────────────────────────────────────

_agent: ChatAgent | None = None
_agent_lock = threading.Lock()
_conversation: Conversation | None = None
_current_provider_key: str = ""


def _get_agent(cfg: dict) -> tuple[ChatAgent, Conversation]:
    global _agent, _conversation, _current_provider_key

    provider_name = cfg.get("provider", "anthropic")
    ai_cfg = cfg.get(provider_name, {})
    api_key = ai_cfg.get("api_key", "").strip()
    model = ai_cfg.get("model", "")
    base_timeout = int(ai_cfg.get("timeout_sec", 30))
    # Scale timeout with max_tokens — long responses need more time
    max_tok = int(cfg.get("max_tokens", 8192))
    extra = 60 if max_tok <= 8192 else 120 if max_tok <= 16384 else 180
    timeout = base_timeout + extra

    key = f"{provider_name}:{model}:{api_key}"

    with _agent_lock:
        if _agent is None or _current_provider_key != key:
            provider = create_provider(provider_name, model)
            _agent = ChatAgent(provider, api_key, timeout)
            _conversation = Conversation()
            _current_provider_key = key
        if _conversation is None:
            _conversation = Conversation()
        return _agent, _conversation


# ── High-level API ─────────────────────────────────────────────

def chat(user_message: str, cfg: dict) -> str:
    """Process user message and return response.

    Hybrid Routing:
      Strict  -> inject DB context, LLM answers without tools
      Creative -> grant tool access, LLM decides autonomously
    """
    from rag.query_router import route, RouteMode

    provider_name = cfg.get("provider", "anthropic")
    ai_cfg = cfg.get(provider_name, {})
    api_key = ai_cfg.get("api_key", "").strip()
    if not api_key and provider_name != "ollama":
        return "API key not configured. Please set your API key in Settings."

    agent, conversation = _get_agent(cfg)
    max_tokens = int(cfg.get("max_tokens", 8192))

    # Place length hint at top of system prompt (highest priority)
    length_hint = _LENGTH_HINTS.get(max_tokens, _LENGTH_HINTS[8192])
    length_prefix = f"[MANDATORY OUTPUT LENGTH]\n{length_hint}\nYou MUST follow the above length requirement. This overrides all other instructions.\n\n"
    strict_prompt = length_prefix + STRICT_PROMPT
    creative_prompt = length_prefix + SYSTEM_PROMPT

    # Routing
    route_result = route(user_message)

    if route_result.mode == RouteMode.STRICT:
        # Strict: inject DB context into user message
        augmented_msg = (
            f"{user_message}\n\n"
            f"[DB lookup results — answer based on this data]\n"
            f"{route_result.db_context}"
        )
        conversation.append(agent.provider.make_user_msg(augmented_msg))
        _LOG.info("[chat] STRICT mode — DB context injected (%d chars)",
                  len(route_result.db_context))
        try:
            # Strict: answer directly without tools (DB data already provided)
            return agent.chat(conversation, {}, strict_prompt, max_tokens=max_tokens)
        except Exception as e:
            _LOG.warning("[chat] strict mode failed, fallback to creative: %s", e)
            # Fallback to creative on failure
            conversation.messages.pop()  # remove failed augmented message

    # Creative: original message + tool access
    conversation.append(agent.provider.make_user_msg(user_message))
    tool_fns = {
        "uesp_search": make_search_fn(cfg),
        "uesp_db": make_db_fn(),
        "lore_search": make_lore_search_fn(cfg),
    }
    _LOG.info("[chat] CREATIVE mode — LLM autonomous with tools (max_tokens=%d)", max_tokens)

    try:
        return agent.chat(conversation, tool_fns, creative_prompt, max_tokens=max_tokens)
    except Exception as e:
        _LOG.warning("[uesp_agent] chat failed: %s", e)
        return f"An error occurred: {e}"


def clear_conversation():
    """Clear conversation history."""
    global _conversation
    with _agent_lock:
        if _conversation:
            _conversation.clear()
