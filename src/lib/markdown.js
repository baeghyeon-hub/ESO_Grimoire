/**
 * 마크다운 렌더링 + ESO 커스텀 태그 처리.
 *
 * 1. [IMG:thumb|full|caption] → 클릭 가능한 이미지
 * 2. [[WikiLink]] → UESP 링크 (노란색)
 * 3. marked v17 bold 버그 우회
 * 4. 잘린 태그 정리
 * 5. **와 [[]] 교차 중첩 해결
 */
import { Marked } from "marked";

const marked = new Marked();
const UESP_BASE = "https://en.uesp.net/wiki/";

// ── 전처리: 교차 중첩 수정 ──────────────────────
function fixCrossNesting(text) {
  // **[[Link]]** → [[Link]]
  text = text.replace(/\*\*\[\[([^\]]+)\]\]\*\*/g, "[[$1]]");
  // **[[Link]] → [[Link]]
  text = text.replace(/\*\*\[\[([^\]]+)\]\]/g, "[[$1]]");
  // [[Link]]** → [[Link]]
  text = text.replace(/\[\[([^\]]+)\]\]\*\*/g, "[[$1]]");
  return text;
}

// ── 플레이스홀더 보호 ────────────────────────────
function protectTags(text) {
  const placeholders = [];
  let idx = 0;

  // [IMG:thumb|full|caption] — caption 안에 [[WikiLink]]가 포함될 수 있음
  text = text.replace(/\[IMG:((?:[^\[\]]|\[\[[^\]]*\]\])*)\]/g, (match) => {
    const key = `%%IMG${idx++}%%`;
    placeholders.push({ key, value: match });
    return key;
  });

  // [[WikiLink]]
  text = text.replace(/\[\[([^\]]+)\]\]/g, (match) => {
    const key = `%%WIKI${idx++}%%`;
    placeholders.push({ key, value: match });
    return key;
  });

  return { text, placeholders };
}

function restoreTags(html, placeholders) {
  for (const { key, value } of placeholders) {
    if (key.includes("IMG")) {
      const inner = value.slice(5, -1); // remove [IMG: and ]
      const parts = inner.split("|");
      const thumb = parts[0] || "";
      const full = parts[1] || thumb;
      const caption = parts[2] || "";
      // caption 안 [[WikiLink]] → plain text (속성용) / HTML (표시용)
      const captionPlain = caption.replace(/\[\[(?:[^:\]]+:)?([^\]]+)\]\]/g, "$1");
      const captionHtml = caption.replace(/\[\[([^\]]+)\]\]/g, (_, wikiInner) => {
        const pIdx = wikiInner.indexOf("|");
        const wTarget = pIdx >= 0 ? wikiInner.slice(0, pIdx).trim() : wikiInner;
        const wCustom = pIdx >= 0 ? wikiInner.slice(pIdx + 1).trim() : null;
        const hasNS = /^(Online|Lore|General|Mod|Tes\d?|Blades|Legends):/.test(wTarget);
        const wUrl = hasNS
          ? `${UESP_BASE}${encodeURIComponent(wTarget.replace(/ /g, "_"))}`
          : `https://en.uesp.net/w/index.php?search=${encodeURIComponent(wTarget)}&go=Go`;
        const display = wCustom || (hasNS ? wTarget.replace(/^[^:]+:/, "") : wTarget);
        return `<a class="wiki-link" href="${wUrl}" target="_blank" rel="noopener">${display}</a>`;
      });
      const imgHtml = `<figure class="msg-img">
        <a href="#" class="image-link" data-full="${full}" data-thumb="${thumb}" data-caption="${captionPlain}" role="button">
          <img src="${thumb}" alt="${captionPlain}" loading="lazy" />
        </a>
        ${caption ? `<figcaption>${captionHtml}</figcaption>` : ""}
      </figure>`;
      html = html.replaceAll(key, imgHtml);
    } else if (key.includes("WIKI")) {
      const inner = value.slice(2, -2); // remove [[ and ]]
      // 파이프 구문 처리: [[Page|Display]] → url=Page, text=Display
      const pipeIdx = inner.indexOf("|");
      const target = pipeIdx >= 0 ? inner.slice(0, pipeIdx).trim() : inner;
      const customDisplay = pipeIdx >= 0 ? inner.slice(pipeIdx + 1).trim() : null;

      const hasNamespace = /^(Online|Lore|General|Mod|Tes\d?|Blades|Legends):/.test(target);
      let url;
      if (hasNamespace) {
        url = `${UESP_BASE}${encodeURIComponent(target.replace(/ /g, "_"))}`;
      } else {
        url = `https://en.uesp.net/w/index.php?search=${encodeURIComponent(target)}&go=Go`;
      }
      // 표시 텍스트: 파이프 뒤 > 네임스페이스 제거 > 원본
      const displayText = customDisplay || (hasNamespace ? target.replace(/^[^:]+:/, "") : target);
      const linkHtml = `<a class="wiki-link" href="${url}" target="_blank" rel="noopener">${displayText}</a>`;
      html = html.replaceAll(key, linkHtml);
    }
  }
  return html;
}

// ── marked v17 bold 버그 우회 ────────────────────
function fixBoldBugs(text) {
  // **"text"**한글 → **"text"** 한글
  text = text.replace(/\*\*([^*]+)\*\*(?=\S)/g, "**$1** ");
  // ** text** → **text**
  text = text.replace(/\*\*\s+([^*]+?)\s*\*\*/g, "**$1**");
  // 홀수 ** 제거 (짝이 안 맞는 bold 마커)
  const count = (text.match(/\*\*/g) || []).length;
  if (count % 2 !== 0) {
    const lastIdx = text.lastIndexOf("**");
    if (lastIdx >= 0) {
      text = text.slice(0, lastIdx) + text.slice(lastIdx + 2);
    }
  }
  return text;
}

// ── 잘린 태그 정리 ───────────────────────────────
function cleanBroken(text) {
  // 불완전한 ]] 제거
  text = text.replace(/(?<!\[)\]\]/g, "");
  // 불완전한 [[ 제거
  text = text.replace(/\[\[(?![^\[]*\]\])/g, "");
  return text;
}

/**
 * 원본 텍스트 → 렌더링된 HTML.
 */
export function renderMarkdown(raw) {
  if (!raw) return "";

  let text = raw;
  text = fixCrossNesting(text);

  // protectTags를 cleanBroken보다 먼저! 유효한 [[Wiki]]와 [IMG:]를 보호한 뒤 잔여 깨진 태그만 정리
  const { text: protected_, placeholders } = protectTags(text);
  let processed = cleanBroken(protected_);
  processed = fixBoldBugs(processed);

  let html = marked.parse(processed);

  // marked가 플레이스홀더를 <p> 등으로 감쌌을 수 있으므로 HTML에서 복원
  html = restoreTags(html, placeholders);

  // marked가 처리 못한 잔여 ** 정리 (플레이스홀더가 섞여서 bold 감지 실패한 경우)
  html = html.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*\*/g, "");

  // h2/h3 섹션을 접이식 아코디언으로 변환
  html = wrapAccordionSections(html);

  return html;
}

// ── 아코디언 섹션 래핑 ──────────────────────────
function wrapAccordionSections(html) {
  // h2 또는 h3가 2개 이상 있을 때만 아코디언 적용
  const headingCount = (html.match(/<h[23][^>]*>/g) || []).length;
  if (headingCount < 2) return html;

  // h2/h3 기준으로 섹션 분리
  const parts = html.split(/(?=<h[23][^>]*>)/);
  if (parts.length < 2) return html;

  let result = "";
  let sectionIdx = 0;
  for (const part of parts) {
    const headingMatch = part.match(/^<(h[23])[^>]*>(.*?)<\/\1>/);
    if (headingMatch) {
      const title = headingMatch[2].replace(/<[^>]+>/g, "");
      const body = part.slice(headingMatch[0].length);
      // 첫 번째 섹션만 open
      const openAttr = sectionIdx === 0 ? " open" : "";
      result += `<details class="accordion"${openAttr}><summary class="accordion-title">${title}</summary><div class="accordion-body"><div class="accordion-body-inner">${body}</div></div></details>`;
      sectionIdx++;
    } else {
      result += part;
    }
  }
  return result;
}
