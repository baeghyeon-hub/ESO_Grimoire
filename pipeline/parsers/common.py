"""
공통 파서 유틸리티 — 모든 도메인 파서가 공유하는 함수.

핵심: extract_template_params() — MediaWiki 템플릿 파라미터 추출.
"""
from __future__ import annotations

import re


def extract_template_params(wikitext: str, template_name: str) -> dict[str, str]:
    """MediaWiki 템플릿에서 named 파라미터를 추출.

    예: {{Online Skill Summary|id=123|line=Dark Magic|cost=2700 Magicka}}
    → {"id": "123", "line": "Dark Magic", "cost": "2700 Magicka"}

    중첩 템플릿/링크 내부의 파이프는 올바르게 처리한다.
    """
    # 템플릿 시작 위치 찾기 (대소문자 무시)
    pattern = re.compile(
        r"\{\{\s*" + re.escape(template_name) + r"\s*\|",
        re.IGNORECASE,
    )
    m = pattern.search(wikitext)
    if not m:
        return {}

    # 중첩 브레이스/브래킷을 고려하여 템플릿 끝 찾기
    start = m.end()
    body = _extract_balanced(wikitext, m.start(), "{{", "}}")
    if not body:
        return {}

    # {{ ... | body ... }} → body 부분만
    inner = body[m.end() - m.start():-2]  # 앞의 {{TemplateName| 와 뒤의 }} 제거

    return _parse_params(inner)


def extract_all_templates(wikitext: str, template_name: str) -> list[dict[str, str]]:
    """같은 이름의 템플릿이 여러 개 있을 때 모두 추출."""
    results = []
    pattern = re.compile(
        r"\{\{\s*" + re.escape(template_name) + r"\s*\|",
        re.IGNORECASE,
    )
    pos = 0
    while pos < len(wikitext):
        m = pattern.search(wikitext, pos)
        if not m:
            break
        body = _extract_balanced(wikitext, m.start(), "{{", "}}")
        if not body:
            pos = m.end()
            continue
        inner = body[m.end() - m.start():-2]
        results.append(_parse_params(inner))
        pos = m.start() + len(body)
    return results


def _extract_balanced(text: str, start: int, open_delim: str, close_delim: str) -> str:
    """중첩 구분자를 고려하여 균형 잡힌 블록 추출."""
    depth = 0
    i = start
    while i < len(text):
        if text[i:i + len(open_delim)] == open_delim:
            depth += 1
            i += len(open_delim)
        elif text[i:i + len(close_delim)] == close_delim:
            depth -= 1
            if depth == 0:
                return text[start:i + len(close_delim)]
            i += len(close_delim)
        else:
            i += 1
    return ""


def _parse_params(inner: str) -> dict[str, str]:
    """템플릿 내부 문자열을 named 파라미터로 분리.

    중첩 {{ }}, [[ ]] 안의 파이프를 무시한다.
    """
    params: dict[str, str] = {}
    parts = _split_params(inner)

    positional = 1
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # named param: key=value
        eq_pos = part.find("=")
        if eq_pos > 0 and not part[:eq_pos].strip().startswith("["):
            key = part[:eq_pos].strip().lower()
            value = part[eq_pos + 1:].strip()
            params[key] = value
        else:
            # positional param
            params[str(positional)] = part
            positional += 1

    return params


def _split_params(inner: str) -> list[str]:
    """파이프(|)로 파라미터 분리 — 중첩 구조 내 파이프 무시."""
    parts = []
    current: list[str] = []
    depth_brace = 0   # {{ }}
    depth_bracket = 0  # [[ ]]

    i = 0
    while i < len(inner):
        ch = inner[i]

        if inner[i:i + 2] == "{{":
            depth_brace += 1
            current.append("{{")
            i += 2
            continue
        elif inner[i:i + 2] == "}}":
            depth_brace = max(0, depth_brace - 1)
            current.append("}}")
            i += 2
            continue
        elif inner[i:i + 2] == "[[":
            depth_bracket += 1
            current.append("[[")
            i += 2
            continue
        elif inner[i:i + 2] == "]]":
            depth_bracket = max(0, depth_bracket - 1)
            current.append("]]")
            i += 2
            continue

        if ch == "|" and depth_brace == 0 and depth_bracket == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1

    if current:
        parts.append("".join(current))

    return parts


# ── Wikitext 정제 유틸 ──────────────────────────────────


def clean_wikitext_inline(text: str) -> str:
    """위키 마크업을 plain text로 변환 (인라인용)."""
    # HTML 코멘트 제거
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # 이미지 마크업 제거: [[File:...|20px|...]] 또는 20px|...|link=...
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\d+px\|[^|•\n]*(?:\|link=[^|•\n]*)?", "", text)
    # [[ON:Page|Display]] → Display
    text = re.sub(r"\[\[(?:ON:|Online:)?[^|\]]*\|([^\]]*)\]\]", r"\1", text)
    # [[ON:Page]] → Page
    text = re.sub(r"\[\[(?:ON:|Online:)?([^\]]*)\]\]", r"\1", text)
    # {{ESO Type Link|value}} → value Type
    text = re.sub(r"\{\{ESO (\w+) (?:Link|Damage Link)(?:\|([^}]*))?\}\}",
                  _expand_eso_link, text)
    text = re.sub(r"\{\{ESO (Spell|Weapon) Damage Link[^}]*\}\}", r"\1 Damage", text)
    # {{Quality Color|...|Name}} → Name
    text = re.sub(r"\{\{ESO Quality Color\|[^|]*\|([^}]*)\}\}", r"\1", text)
    # 남은 템플릿 제거
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # HTML 태그
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    # '''bold'''
    text = re.sub(r"'{2,3}", "", text)
    # __NOTOC__ 등
    text = re.sub(r"__[A-Z]+__", "", text)
    return text.strip()


def _expand_eso_link(m: re.Match) -> str:
    stat_type = m.group(1)
    params_str = m.group(2) or ""
    params = [p.strip() for p in params_str.split("|") if p.strip() and p.strip() != "y"]
    if not params:
        return stat_type
    value = params[0] if re.match(r"[\d\-\.%]", params[0]) else ""
    suffix = ""
    for p in params:
        if p in ("Maximum", "Recovery"):
            suffix = p
        elif not re.match(r"[\d\-\.%]", p) and p not in ("y", ""):
            suffix = p
    parts = []
    if value:
        parts.append(value)
    if suffix:
        parts.extend([stat_type, suffix])
    else:
        parts.append(stat_type)
    return " ".join(parts)


def get_section(wikitext: str, heading: str, level: int = 2) -> str:
    """특정 제목의 섹션 내용을 추출.

    예: get_section(wikitext, "Bosses", level=3) → ===Bosses=== 아래 내용
    """
    eq = "=" * level
    pattern = re.compile(
        rf"^{eq}\s*{re.escape(heading)}\s*{eq}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(wikitext)
    if not m:
        return ""

    start = m.end()
    # 같은 또는 상위 레벨의 다음 헤딩 찾기
    next_heading = re.compile(rf"^={{{1},{level}}}\s*[^=]", re.MULTILINE)
    n = next_heading.search(wikitext, start)
    end = n.start() if n else len(wikitext)
    return wikitext[start:end].strip()


def get_intro(wikitext: str) -> str:
    """첫 섹션 헤딩 이전의 인트로 텍스트."""
    m = re.search(r"^==[^=]", wikitext, re.MULTILINE)
    return wikitext[:m.start()].strip() if m else wikitext.strip()


def extract_list_items(text: str) -> list[str]:
    """위키 리스트 항목 추출 (* 또는 # 시작)."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("*") or line.startswith("#"):
            item = re.sub(r"^[*#]+\s*", "", line).strip()
            if item:
                items.append(item)
    return items
