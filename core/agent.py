"""
대화 엔진 — Provider 기반 LLM 대화 루프.

ESO 로직과 무관한 순수 대화 엔진.
Provider가 tool을 호출하면 tool_fns에서 실행하고 결과를 돌려보내는 루프를 처리한다.
"""
from __future__ import annotations

import logging

import requests

from core.providers import Provider

_LOG = logging.getLogger(__name__)


class Conversation:
    """대화 히스토리를 유지하는 세션."""

    def __init__(self, max_history: int = 20):
        self.messages: list[dict] = []
        self.max_history = max_history

    def append(self, msg: dict | list[dict]):
        if isinstance(msg, list):
            self.messages.extend(msg)
        else:
            self.messages.append(msg)
        self._trim()

    def clear(self):
        self.messages.clear()

    def _trim(self):
        """히스토리를 max_history 이하로 줄이되, tool call/result 쌍을 깨지 않는다.

        Gemini는 functionCall 직후 functionResponse가 와야 하므로
        tool 관련 메시지 중간에서 자르면 400 에러가 발생한다.
        안전한 지점(일반 user 텍스트 메시지의 시작)에서만 자른다.
        """
        if len(self.messages) <= self.max_history:
            return

        # 안전한 자르기 시작점 찾기:
        # "일반 user 메시지" 위치에서만 자를 수 있다.
        # 그 위치에서 자르면 그 이후 메시지만 남기므로,
        # 남는 첫 메시지가 반드시 일반 user 메시지여야 한다.
        best_cut = None
        for i, msg in enumerate(self.messages):
            remaining = len(self.messages) - i
            if remaining <= 4:
                break  # 최소 4개는 유지 (user + assistant + tool + result)
            if remaining > self.max_history:
                # 아직 더 잘라야 함 — 안전한 지점이면 후보로 기록
                if self._is_plain_user_msg(msg):
                    best_cut = i
                continue
            # remaining <= max_history — 이 지점에서 자르면 OK
            if self._is_plain_user_msg(msg):
                self.messages = self.messages[i:]
                return
            # 이 위치가 tool 메시지라면, 가장 최근 안전 지점 사용
            if best_cut is not None:
                self.messages = self.messages[best_cut:]
                return
            break

        # 안전한 지점이 없으면 — 전체를 검사해서 가장 마지막 안전 지점 사용
        if best_cut is not None:
            self.messages = self.messages[best_cut:]
            return

        # 정말로 안전한 지점이 없으면 (모두 tool 메시지) — 히스토리 초기화
        _LOG.warning("[conversation] No safe trim point found, clearing history")
        self.messages.clear()

    @staticmethod
    def _is_plain_user_msg(msg: dict) -> bool:
        """tool result가 아닌 일반 user 메시지인지 판별."""
        role = msg.get("role", "")
        if role == "tool":
            return False  # OpenAI tool result
        if role != "user":
            return False
        # Anthropic: content가 list이고 tool_result 포함
        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    return False
        # Gemini: parts에 functionResponse 포함
        parts = msg.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and "functionResponse" in part:
                    return False
        return True


class ChatAgent:
    """Provider 기반 대화형 에이전트 엔진.

    system_prompt와 tool_fns를 외부에서 주입받아
    특정 도메인에 종속되지 않는 범용 LLM 대화 루프를 제공한다.
    """

    def __init__(self, provider: Provider, api_key: str, timeout_sec: int = 30):
        self._provider = provider
        self._api_key = api_key
        self._timeout = timeout_sec
        self._session = requests.Session()

    @property
    def provider(self) -> Provider:
        return self._provider

    def chat(
        self,
        conversation: Conversation,
        tool_fns: dict,
        system_prompt: str,
        max_tokens: int = 8192,
        max_tool_rounds: int = 6,
    ) -> str:
        """대화를 처리하고 최종 텍스트 응답을 반환."""
        use_tools = bool(tool_fns)
        for round_idx in range(max_tool_rounds):
            try:
                data = self._call_api(conversation.messages, system_prompt, max_tokens, use_tools)
            except RuntimeError as e:
                _LOG.error("[agent] API call failed (round %d): %s", round_idx + 1, e)
                # API 에러 시 히스토리에서 마지막 tool 관련 메시지 정리 후 에러 반환
                raise
            parsed = self._provider.parse_response(data)

            # 어시스턴트 응답을 히스토리에 추가
            conversation.append(self._provider.make_assistant_msg(parsed.raw_content))

            if parsed.tool_calls:
                results = []
                for tc in parsed.tool_calls:
                    fn = tool_fns.get(tc.name)
                    if not fn:
                        results.append((tc.id, f"Unknown tool: {tc.name}"))
                        continue

                    _LOG.info("[agent] tool call [round %d]: %s(%r)",
                              round_idx + 1, tc.name, tc.arguments)
                    try:
                        result = fn(**tc.arguments)
                    except Exception as e:
                        result = f"Tool error: {e}"
                    results.append((tc.id, result))

                # tool 결과를 히스토리에 추가
                conversation.append(self._provider.make_tool_result_msgs(results))
                continue

            return parsed.text

        return "검색 횟수 제한에 도달했어. 질문을 좀 더 구체적으로 해줘."

    def _call_api(self, messages: list[dict], system_prompt: str,
                   max_tokens: int, use_tools: bool = True) -> dict:
        headers = self._provider.build_headers(self._api_key)
        payload = self._provider.build_payload(messages, system_prompt, max_tokens)

        # Strict 모드: tool 제거 + thinking 비활성화 (빠른 직답)
        if not use_tools:
            payload.pop("tools", None)
            # Gemini thinking 모델: 불필요한 추론 비활성화
            gen_cfg = payload.get("generationConfig")
            if gen_cfg is not None:
                gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}

        try:
            resp = self._session.post(
                self._provider.api_url, headers=headers, json=payload, timeout=self._timeout,
            )
        except requests.ConnectionError:
            url = self._provider.api_url
            if "localhost:11434" in url:
                raise RuntimeError(
                    "Ollama 서버가 실행 중이 아니야. "
                    "터미널에서 `ollama serve`를 실행하거나 Ollama 앱을 시작해줘."
                )
            raise RuntimeError(f"서버에 연결할 수 없어: {url}")
        if resp.status_code != 200:
            raise RuntimeError(f"API HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()
