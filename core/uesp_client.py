"""
UESP Cloudflare Worker 프록시 클라이언트.

워커 엔드포인트에 검색/조회 요청을 보내고 결과를 반환한다.
"""
from __future__ import annotations

import logging
import threading

import requests

_LOG = logging.getLogger(__name__)

class UESPClient:
    """UESP 워커 프록시에 요청을 보내는 HTTP 클라이언트."""

    def __init__(self, worker_url: str, timeout_sec: int = 10):
        self._base = worker_url.rstrip("/")
        self._timeout = timeout_sec
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "ESO-Translator/3.0"

    def health(self) -> dict:
        return self._get({"action": "health"})

    def search(self, query: str, *, limit: int = 5, search_type: str = "") -> dict:
        params: dict = {"action": "search", "q": query, "limit": str(limit)}
        if search_type:
            params["type"] = search_type
        return self._get(params)

    def resolve(self, query: str, *, search_type: str = "") -> dict:
        params: dict = {"action": "resolve", "q": query}
        if search_type:
            params["type"] = search_type
        return self._get(params)

    def page(self, title: str) -> dict:
        return self._get({"action": "page", "q": title})

    def full(self, title: str) -> dict:
        return self._get({"action": "full", "q": title})

    def sections(self, title: str) -> dict:
        return self._get({"action": "sections", "q": title})

    def section(self, title: str, section_idx: int) -> dict:
        return self._get({"action": "section", "q": title, "section": str(section_idx)})

    def _get(self, params: dict) -> dict:
        try:
            resp = self._session.get(self._base, params=params, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            return {"ok": False, "error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"ok": False, "error": "connection_failed"}
        except Exception as e:
            _LOG.warning("[uesp_client] request failed: %s", e)
            return {"ok": False, "error": str(e)}


# ── UESP MediaWiki 이미지 API (직접 호출, 워커 불필요) ──────────

_UESP_API = "https://en.uesp.net/w/api.php"

# 유용한 이미지 접두사 패턴 (우선순위 순)
_IMAGE_PRIORITIES = {
    "map": 1,       # ON-map-*.jpg — 던전/존 맵
    "place": 2,     # ON-place-*.jpg — 장소 스크린샷
    "load": 3,      # ON-load-*.jpg — 로딩 화면
    "icon-armor": 4,  # ON-icon-armor-*.png — 세트 아이콘
    "icon-skill": 5,  # ON-icon-skill-*.png — 스킬 아이콘
    "npc": 6,       # ON-npc-*.jpg — NPC
    "creature": 7,  # ON-creature-*.jpg — 크리쳐/보스
    "item": 8,      # ON-item-*.png — 아이템
    "interior": 9,  # ON-interior-*.jpg — 내부
}


def _image_priority(filename: str) -> int:
    """이미지 파일명에서 우선순위 반환 (낮을수록 중요)."""
    name_lower = filename.lower()
    for prefix, priority in _IMAGE_PRIORITIES.items():
        if prefix in name_lower:
            return priority
    return 99


def fetch_page_images(
    title: str,
    *,
    thumb_width: int = 400,
    max_images: int = 6,
    timeout: int = 10,
) -> list[dict]:
    """UESP 페이지의 이미지 목록을 가져와 썸네일 URL 포함 반환.

    Returns:
        [{"title": "File:ON-map-...", "url": "https://...", "thumb": "https://...",
          "width": 768, "height": 768, "type": "map"}, ...]
    """
    session = requests.Session()
    session.headers["User-Agent"] = "ESO-UESP-RAG/1.0"

    # 1) 페이지에 포함된 이미지 목록
    resp = session.get(_UESP_API, params={
        "action": "query",
        "titles": title,
        "prop": "images",
        "format": "json",
        "imlimit": "50",
    }, timeout=timeout)
    resp.raise_for_status()

    pages = resp.json().get("query", {}).get("pages", {})
    all_images = []
    for page in pages.values():
        all_images.extend(page.get("images", []))

    if not all_images:
        return []

    # 2) 화이트리스트 방식 — 유용한 이미지만 통과
    useful = []
    # 허용하는 파일명 패턴 (이것 중 하나를 포함해야 통과)
    allow_patterns = {
        "on-map-", "on-place-", "on-load-", "on-interior-",
        "on-npc-", "on-creature-", "on-item-",
        "icon-armor-", "icon-skill-", "icon-fragment-",
        "icon-weapon-", "icon-jewelry-", "icon-style-",
        "icon-consumable-", "icon-furnishing-",
        # Lore namespace images
        "lo-map-", "lo-place-", "lo-misc-", "lo-creature-",
        "lo-npc-", "lo-char-", "lo-race-", "lo-banner-",
        "sr-map-", "sr-place-", "sr-npc-", "sr-creature-",
        "mw-map-", "mw-place-", "mw-npc-", "mw-creature-",
        "ob-map-", "ob-place-", "ob-npc-", "ob-creature-",
        "lore-", "lore_",
    }
    for img in all_images:
        name = img["title"].lower()
        if any(p in name for p in allow_patterns):
            useful.append(img)

    # 우선순위로 정렬, 상위 max_images개
    useful.sort(key=lambda x: _image_priority(x["title"]))
    useful = useful[:max_images]

    if not useful:
        return []

    # 3) imageinfo로 실제 URL + 썸네일 가져오기
    titles_str = "|".join(img["title"] for img in useful)
    resp2 = session.get(_UESP_API, params={
        "action": "query",
        "titles": titles_str,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": str(thumb_width),
        "format": "json",
    }, timeout=timeout)
    resp2.raise_for_status()

    pages2 = resp2.json().get("query", {}).get("pages", {})
    results = []
    for page in pages2.values():
        # missing 이미지 건너뛰기
        if page.get("missing") is not None or "imagerepository" in page and page["imagerepository"] == "":
            continue
        info_list = page.get("imageinfo", [])
        if not info_list:
            continue
        info = info_list[0]
        file_title = page.get("title", "")
        url = info.get("url", "")
        thumb = info.get("thumburl", url)

        # URL이 없으면 건너뛰기
        if not url:
            continue

        # 이미지 유형 분류
        img_type = "other"
        name_lower = file_title.lower()
        for prefix in _IMAGE_PRIORITIES:
            if prefix in name_lower:
                img_type = prefix.replace("-", "_")
                break

        results.append({
            "title": file_title,
            "url": url,
            "thumb": thumb,
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "mime": info.get("mime", ""),
            "type": img_type,
        })

    # 다시 우선순위로 정렬
    results.sort(key=lambda x: _image_priority(x["title"]))
    return results


_clients: dict[str, UESPClient] = {}
_clients_lock = threading.Lock()


def get_client(worker_url: str, timeout_sec: int = 10) -> UESPClient:
    with _clients_lock:
        key = worker_url
        if key not in _clients:
            _clients[key] = UESPClient(worker_url, timeout_sec)
        client = _clients[key]
        client._timeout = timeout_sec
        return client


def lookup(query: str, cfg: dict) -> dict:
    """High-level: resolve → sections → section 으로 전체 페이지 내용 가져옴.

    MediaWiki extracts API는 테이블 데이터를 잘라먹으므로,
    sections + section (wikitext) 방식으로 전체 내용을 가져온다.
    """
    uesp_cfg = cfg.get("uesp_lookup", {})
    if not uesp_cfg.get("enabled"):
        return {"ok": False, "error": "disabled"}

    worker_url = uesp_cfg.get("worker_url", "").strip()
    if not worker_url:
        return {"ok": False, "error": "no_worker_url"}

    timeout = int(uesp_cfg.get("timeout_sec", 10))
    client = get_client(worker_url, timeout)

    # 1) resolve로 검색 + 제목 확인
    resolved = client.resolve(query)
    if not resolved.get("ok") or not resolved.get("found"):
        return resolved

    title = resolved.get("resolvedTitle", "")
    if not title:
        return resolved

    search_hit = resolved.get("searchHit", {})

    # 2) URL 확보 (full에서 fullurl 추출)
    url = ""
    full_data = client.full(title)
    full_pages = full_data.get("page", [])
    if isinstance(full_pages, list) and full_pages:
        url = full_pages[0].get("fullurl", "")
    elif isinstance(full_pages, dict):
        pages = full_pages.get("query", {}).get("pages", [])
        if pages:
            p = pages[0] if isinstance(pages, list) else next(iter(pages.values()), {})
            url = p.get("fullurl", "")

    # 3) sections 목록 가져오기
    sections_data = client.sections(title)
    sections_list = sections_data.get("sections", [])

    # 4) intro (section 0) + 각 섹션의 wikitext 가져오기
    parts = []

    # intro (section index 0)
    intro_data = client.section(title, 0)
    intro_text = intro_data.get("wikitext", "").strip()
    if intro_text:
        parts.append(intro_text)

    # 나머지 섹션 (최대 10개)
    for sec in sections_list[:10]:
        idx = sec.get("index", 0)
        if idx == 0:
            continue
        sec_data = client.section(title, int(idx))
        wikitext = sec_data.get("wikitext", "").strip()
        if wikitext:
            parts.append(wikitext)

    extract = "\n\n".join(parts)

    # wikitext에서 불필요한 마크업 정리 (기본적인 것만)
    extract = _clean_wikitext(extract)

    return {
        "ok": True,
        "found": bool(extract),
        "resolvedTitle": title,
        "extract": extract,
        "url": url,
        "searchHit": search_hit,
    }


def _clean_wikitext(text: str) -> str:
    """위키텍스트에서 LLM이 읽기 쉽게 기본 마크업 정리."""
    import re

    # [[ON:Page|Display]] → Display, [[ON:Page]] → Page
    text = re.sub(r'\[\[(?:ON:|Online:)?([^|\]]*)\|([^\]]*)\]\]', r'\2', text)
    text = re.sub(r'\[\[(?:ON:|Online:)?([^\]]*)\]\]', r'\1', text)

    # {{Item Link|Name|...}} → Name
    text = re.sub(r'\{\{Item Link\|([^|}]+)[^}]*\}\}', r'\1', text)

    # {{ThickLine}}, {{Mod Header|...}}, {{Trail|...}}, {{icon|...}}, {{about|...}},
    # {{Online Update|...}} 등 불필요한 템플릿 제거
    text = re.sub(r'\{\{ThickLine\}\}', '', text)
    text = re.sub(r'\{\{(?:Mod Header|Trail|icon|about|Online Update|Lore Link|Skill Link)[^}]*\}\}', '', text)

    # {{ESO Sets|...}} 같은 남은 템플릿: 이름만 추출
    text = re.sub(r'\{\{ESO Sets\|([^|}]+)[^}]*\}\}', r'\1', text)

    # 남은 {{...}} 템플릿 제거 (중첩 포함, 최대 3단계 반복)
    for _ in range(3):
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)

    # __NOTOC__, __TOC__ 등 매직워드 제거
    text = re.sub(r'__[A-Z]+__', '', text)

    # [[File:...]] 이미지 태그 제거
    text = re.sub(r'\[\[File:[^\]]*\]\]', '', text)

    # [[Category:...]] 카테고리 제거
    text = re.sub(r'\[\[Category:[^\]]*\]\]', '', text)

    # {| class="wikitable" ... |} 테이블을 읽기 쉽게 변환
    text = _convert_wiki_tables(text)

    # 위키 이탤릭/볼드 마크업: '''bold''' → bold, ''italic'' → italic
    text = re.sub(r"'{3}(.+?)'{3}", r'\1', text)
    text = re.sub(r"'{2}(.+?)'{2}", r'\1', text)

    # 남은 HTML 태그 정리
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)

    # 테이블에서 남은 이미지 크기 아티팩트 (40px 등)
    text = re.sub(r'\b\d+px\b', '', text)

    # 연속 빈 줄 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 줄 시작/끝 공백 정리
    text = re.sub(r' +\| ', ' | ', text)

    return text.strip()


def _convert_wiki_tables(text: str) -> str:
    """위키 테이블을 텍스트 형식으로 변환."""
    import re

    def _process_table(match: re.Match) -> str:
        table_text = match.group(0)
        rows = []
        current_row: list[str] = []
        headers: list[str] = []

        for line in table_text.split('\n'):
            line = line.strip()
            if line.startswith('{|') or line.startswith('|}'):
                continue
            if line.startswith('!'):
                # 헤더 행
                cells = re.split(r'!!', line.lstrip('! '))
                headers = [c.strip() for c in cells]
            elif line.startswith('|-'):
                if current_row:
                    rows.append(current_row)
                    current_row = []
            elif line.startswith('|'):
                cells = re.split(r'\|\|', line.lstrip('| '))
                for c in cells:
                    c = c.strip()
                    if c and not c.startswith('colspan'):
                        current_row.append(c)

        if current_row:
            rows.append(current_row)

        if not rows and not headers:
            return ""

        result_lines = []
        if headers:
            result_lines.append(" | ".join(headers))
            result_lines.append("-" * 40)
        for row in rows:
            result_lines.append(" | ".join(row))

        return "\n".join(result_lines)

    return re.sub(r'\{\|.*?\|\}', _process_table, text, flags=re.DOTALL)

