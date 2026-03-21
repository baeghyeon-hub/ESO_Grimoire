"""
멀티 프로바이더 지원 — Anthropic, OpenAI, Google Gemini.

각 프로바이더는 API 호출 형식, 응답 파싱, 대화 메시지 포맷을 처리한다.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

_LOG = logging.getLogger(__name__)

# ── Tool 정의 (프로바이더 무관 스키마) ──────────────────────

_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "English search term for UESP wiki",
        },
    },
    "required": ["query"],
}

_TOOL_NAME = "uesp_search"
_TOOL_DESC = "Search UESP wiki. English terms only."

_DB_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["get_set", "search_sets", "filter_sets", "search_text", "search_by_stat"],
            "description": "get_set=exact name, search_sets=partial, filter_sets=by type/armor/loc, search_text=FTS, search_by_stat=by stat",
        },
        "query": {"type": "string", "description": "Search term"},
        "set_type": {"type": "string", "description": "overland/dungeon/trial/craftable/mythic/monster/arena/pvp"},
        "armor_type": {"type": "string", "description": "light/medium/heavy"},
        "location": {"type": "string", "description": "Drop location"},
    },
    "required": ["action"],
}

_DB_TOOL_NAME = "uesp_db"
_DB_TOOL_DESC = "Query local ESO DB for set data. Faster than wiki. English names only."

TOOLS = [
    {"name": _TOOL_NAME, "description": _TOOL_DESC, "schema": _TOOL_SCHEMA},
    {"name": _DB_TOOL_NAME, "description": _DB_TOOL_DESC, "schema": _DB_TOOL_SCHEMA},
]


# ── 프로바이더 공통 데이터 ──────────────────────────────────

@dataclass
class ToolCall:
    """프로바이더 무관 tool call 표현."""
    id: str
    name: str
    arguments: dict


@dataclass
class ParsedResponse:
    """프로바이더 무관 API 응답 파싱 결과."""
    raw_content: object   # 프로바이더별 원본 (대화 히스토리용)
    tool_calls: list[ToolCall]
    text: str


# ── 프로바이더 인터페이스 ──────────────────────────────────

class Provider(ABC):
    """프로바이더 베이스 클래스."""

    def __init__(self, model: str):
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    @abstractmethod
    def api_url(self) -> str: ...

    @abstractmethod
    def build_headers(self, api_key: str) -> dict: ...

    @abstractmethod
    def build_payload(self, messages: list, system_prompt: str, max_tokens: int) -> dict: ...

    @abstractmethod
    def parse_response(self, data: dict) -> ParsedResponse: ...

    @abstractmethod
    def make_assistant_msg(self, raw_content) -> dict: ...

    @abstractmethod
    def make_tool_result_msgs(self, results: list[tuple[str, str]]) -> list[dict]:
        """tool 결과를 대화에 추가할 메시지 목록으로 변환.
        results: [(tool_call_id_or_name, result_text), ...]
        """
        ...

    @abstractmethod
    def make_user_msg(self, text: str) -> dict: ...


# ── Anthropic ──────────────────────────────────────────────

class AnthropicProvider(Provider):

    @property
    def api_url(self) -> str:
        return "https://api.anthropic.com/v1/messages"

    def build_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def build_payload(self, messages: list, system_prompt: str, max_tokens: int) -> dict:
        return {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "system": system_prompt,
            "tools": [
                {"name": t["name"], "description": t["description"], "input_schema": t["schema"]}
                for t in TOOLS
            ],
            "messages": messages,
        }

    def parse_response(self, data: dict) -> ParsedResponse:
        content = data.get("content", [])
        tool_calls = []
        text_parts = []
        for block in content:
            if block.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block.get("name", ""),
                    arguments=block.get("input", {}),
                ))
            elif block.get("type") == "text":
                t = block.get("text", "")
                if t:
                    text_parts.append(t)
        return ParsedResponse(
            raw_content=content,
            tool_calls=tool_calls,
            text="\n".join(text_parts).strip(),
        )

    def make_assistant_msg(self, raw_content) -> dict:
        return {"role": "assistant", "content": raw_content}

    def make_tool_result_msgs(self, results: list[tuple[str, str]]) -> list[dict]:
        return [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": text}
                for tid, text in results
            ],
        }]

    def make_user_msg(self, text: str) -> dict:
        return {"role": "user", "content": text}


# ── OpenAI ─────────────────────────────────────────────────

class OpenAIProvider(Provider):

    @property
    def api_url(self) -> str:
        return "https://api.openai.com/v1/chat/completions"

    def build_headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(self, messages: list, system_prompt: str, max_tokens: int) -> dict:
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        return {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "tools": [
                {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["schema"]}}
                for t in TOOLS
            ],
            "messages": all_messages,
        }

    def parse_response(self, data: dict) -> ParsedResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = []
        for tc in message.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                id=tc["id"],
                name=fn.get("name", ""),
                arguments=args,
            ))
        text = (message.get("content") or "").strip()
        return ParsedResponse(
            raw_content=message,
            tool_calls=tool_calls,
            text=text,
        )

    def make_assistant_msg(self, raw_content) -> dict:
        msg: dict = {"role": "assistant"}
        if raw_content.get("content"):
            msg["content"] = raw_content["content"]
        else:
            msg["content"] = None
        if raw_content.get("tool_calls"):
            msg["tool_calls"] = raw_content["tool_calls"]
        return msg

    def make_tool_result_msgs(self, results: list[tuple[str, str]]) -> list[dict]:
        # OpenAI는 tool 결과를 개별 메시지로
        return [
            {"role": "tool", "tool_call_id": tid, "content": text}
            for tid, text in results
        ]

    def make_user_msg(self, text: str) -> dict:
        return {"role": "user", "content": text}


# ── Google Gemini ──────────────────────────────────────────

class GoogleProvider(Provider):

    @property
    def api_url(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"

    def build_headers(self, api_key: str) -> dict:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

    def build_payload(self, messages: list, system_prompt: str, max_tokens: int) -> dict:
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": messages,
            "tools": [{"functionDeclarations": [
                {"name": t["name"], "description": t["description"], "parameters": t["schema"]}
                for t in TOOLS
            ]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0,
            },
        }

    def parse_response(self, data: dict) -> ParsedResponse:
        candidates = data.get("candidates", [])
        if not candidates:
            error = data.get("error", {}).get("message", "No candidates")
            return ParsedResponse(raw_content=[], tool_calls=[], text=f"API error: {error}")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        tool_calls = []
        text_parts = []
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(ToolCall(
                    id=fc.get("name", ""),
                    name=fc.get("name", ""),
                    arguments=fc.get("args", {}),
                ))
            elif "text" in part:
                text_parts.append(part["text"])

        return ParsedResponse(
            raw_content=parts,
            tool_calls=tool_calls,
            text="\n".join(text_parts).strip(),
        )

    def make_assistant_msg(self, raw_content) -> dict:
        return {"role": "model", "parts": raw_content}

    def make_tool_result_msgs(self, results: list[tuple[str, str]]) -> list[dict]:
        return [{
            "role": "user",
            "parts": [
                {"functionResponse": {"name": name, "response": {"result": text}}}
                for name, text in results
            ],
        }]

    def make_user_msg(self, text: str) -> dict:
        return {"role": "user", "parts": [{"text": text}]}


# ── Ollama (로컬 LLM — OpenAI 호환) ─────────────────────

class OllamaProvider(OpenAIProvider):
    """Ollama 로컬 서버 — OpenAI 호환 API 재활용."""

    @property
    def api_url(self) -> str:
        return "http://localhost:11434/v1/chat/completions"

    def build_headers(self, api_key: str) -> dict:
        # Ollama는 인증 불필요, 빈 헤더
        return {"Content-Type": "application/json"}

    def build_payload(self, messages: list, system_prompt: str, max_tokens: int) -> dict:
        payload = super().build_payload(messages, system_prompt, max_tokens)
        # Ollama는 tool 지원이 모델마다 다름 — 지원 안 하면 제거 필요
        # temperature 약간 올려서 자연스럽게
        payload["temperature"] = 0.3
        return payload


# ── 프로바이더 레지스트리 ──────────────────────────────────

PROVIDERS: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "ollama": OllamaProvider,
}

PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "anthropic": [
        ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
    ],
    "openai": [
        ("gpt-4o-mini", "GPT-4o Mini"),
        ("gpt-4o", "GPT-4o"),
        ("gpt-4.1-mini", "GPT-4.1 Mini"),
        ("gpt-4.1-nano", "GPT-4.1 Nano"),
    ],
    "google": [
        ("gemini-2.0-flash", "Gemini 2.0 Flash"),
        ("gemini-2.5-flash-preview-05-20", "Gemini 2.5 Flash"),
        ("gemini-3-flash-preview", "Gemini 3 Flash"),
    ],
    "ollama": [
        ("qwen3:8b", "Qwen3 8B"),
        ("gemma3:12b", "Gemma3 12B"),
        ("llama3.1:8b", "Llama 3.1 8B"),
    ],
}

PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "google": "Google (Gemini)",
    "ollama": "Ollama (Local)",
}


def create_provider(name: str, model: str) -> Provider:
    """프로바이더 이름과 모델로 인스턴스 생성."""
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}")
    return cls(model)
