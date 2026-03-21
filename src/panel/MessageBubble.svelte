<script>
  import { renderMarkdown } from "../lib/markdown.js";
  import { t } from "../lib/i18n.js";

  import { open } from "@tauri-apps/plugin-shell";
  import { openImageViewer } from "../lib/windowManager.js";

  let { role = "user", content = "" } = $props();

  let html = $derived(role === "assistant" ? renderMarkdown(content) : escapeHtml(content));

  let popup = $state(null); // { text, x, y, url }
  let bubbleEl;

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\n/g, "<br>");
  }

  async function copyText() {
    const plain = content.replace(/\[IMG:[^\]]+\]/g, "").replace(/\[\[([^\]]+)\]\]/g, "$1");
    await navigator.clipboard.writeText(plain);
  }

  // 이미지 클릭 → 이미지 뷰어 열기 (같은 버블의 모든 이미지 수집)
  async function handleImageClick(e) {
    const imageLink = e.target.closest("a.image-link");
    if (!imageLink) return;

    e.preventDefault();
    e.stopPropagation();

    const imageData = {
      url: imageLink.getAttribute("data-full"),
      thumb: imageLink.getAttribute("data-thumb"),
      title: imageLink.getAttribute("data-caption"),
      source: "external"
    };

    // 같은 버블 내 모든 이미지 링크 수집
    const bubble = imageLink.closest(".content") || imageLink.closest(".bubble");
    const allLinks = bubble ? bubble.querySelectorAll("a.image-link") : [];
    const allImages = Array.from(allLinks).map(link => ({
      url: link.getAttribute("data-full"),
      thumb: link.getAttribute("data-thumb"),
      title: link.getAttribute("data-caption"),
      source: "external"
    }));

    await openImageViewer(imageData, allImages.length > 1 ? allImages : null);
  }

  // WikiLink 클릭 → 미니 팝업
  function handleWikiLinkClick(e) {
    const link = e.target.closest("a.wiki-link");
    if (!link) {
      if (popup) popup = null;
      return;
    }
    e.preventDefault();
    e.stopPropagation();

    const rect = link.getBoundingClientRect();
    const popupW = 210, popupH = 110;

    // viewport 기준 fixed 좌표
    let x = rect.left;
    if (x + popupW > window.innerWidth) x = window.innerWidth - popupW - 8;
    if (x < 4) x = 4;

    let y = rect.bottom + 4;
    if (y + popupH > window.innerHeight) y = rect.top - popupH - 4;
    if (y < 4) y = 4;

    popup = {
      text: link.textContent,
      url: link.href,
      x,
      y,
    };
  }

  // 통합 클릭 핸들러: 이미지 클릭 먼저 확인
  function handleContentClick(e) {
    // 이미지 링크 확인
    const imageLink = e.target.closest("a.image-link");
    if (imageLink) {
      handleImageClick(e);
      return;
    }

    // WikiLink 확인
    const wikiLink = e.target.closest("a.wiki-link");
    if (wikiLink) {
      handleWikiLinkClick(e);
      return;
    }

    // 다른 것 클릭 시 팝업 닫기
    if (popup) popup = null;
  }

  function closePopup() {
    popup = null;
  }

  async function openLink() {
    if (popup) {
      try { await open(popup.url); } catch {}
    }
    popup = null;
  }

  function searchKeyword() {
    if (popup) {
      // 해당 키워드로 새 질문 전송 (부모로 이벤트 버블링)
      const event = new CustomEvent("wikisearch", { detail: popup.text, bubbles: true });
      bubbleEl.dispatchEvent(event);
    }
    popup = null;
  }

</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="bubble {role}" bind:this={bubbleEl} onclick={handleContentClick}>
  <div class="label">{role === "user" ? t("user_label") : t("bot_label")}</div>
  <div class="content">{@html html}</div>

  {#if role === "assistant"}
    <div class="actions">
      <button onclick={copyText} title={t("copy")}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="3" width="12" height="16" rx="1.5"/><path d="M4 7V21H16" stroke-dasharray="2 2" opacity="0.5"/><line x1="11" y1="8" x2="17" y2="8" opacity="0.4"/><line x1="11" y1="11" x2="17" y2="11" opacity="0.4"/><line x1="11" y1="14" x2="15" y2="14" opacity="0.4"/></svg>
      </button>
    </div>
  {/if}
</div>

<!-- WikiLink 미니 팝업 (fixed, bubble 밖) -->
{#if popup}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="wiki-popup-fixed" style="left:{popup.x}px; top:{popup.y}px" onclick={(e) => e.stopPropagation()}>
    <div class="wiki-popup-title">{popup.text}</div>
    <div class="wiki-popup-actions">
      <button onclick={searchKeyword}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M16 16L21 21"/></svg>
        {t("ask_grimoire")}
      </button>
      <button onclick={openLink}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        {t("uesp_wiki")}
      </button>
    </div>
    <button class="wiki-popup-close" onclick={closePopup}>✕</button>
  </div>
{/if}

<style>
  .bubble {
    max-width: 100%;
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.6;
    word-break: break-word;
  }
  .user {
    align-self: flex-end;
    background: rgba(50, 40, 28, var(--bg-alpha, 0.9));
    border: 1px solid rgba(200, 168, 78, 0.1);
    border-bottom-right-radius: 4px;
  }
  .assistant {
    align-self: flex-start;
    background: rgba(38, 30, 20, var(--bg-alpha, 0.9));
    border: 1px solid rgba(200, 168, 78, 0.06);
    border-bottom-left-radius: 4px;
  }
  .label {
    font-size: 10px;
    color: #9a8a68;
    margin-bottom: 4px;
    font-weight: 600;
  }
  .content {
    color: #e8dcc8;
  }
  .content :global(strong) {
    color: #f0dca0;
  }
  .content :global(a) {
    color: #c8a84e;
    text-decoration: none;
  }
  .content :global(a:hover) {
    text-decoration: underline;
  }
  .content :global(a.wiki-link) {
    color: #f0c050;
    font-weight: 600;
    border-bottom: 1px dotted rgba(240, 192, 80, 0.4);
  }
  .content :global(a.wiki-link:hover) {
    color: #ffe080;
    border-bottom-color: rgba(255, 224, 128, 0.6);
  }
  .content :global(h1), .content :global(h2), .content :global(h3) {
    font-family: 'Cinzel', serif;
    color: #d4b860;
    margin: 8px 0 4px;
  }
  .content :global(.msg-img) {
    margin: 8px 0;
  }
  .content :global(.msg-img img) {
    max-width: 100%;
    border-radius: 2px;
    border: 2px solid rgba(200, 168, 78, 0.3);
    box-shadow:
      0 0 0 1px rgba(0, 0, 0, 0.4),
      0 2px 8px rgba(0, 0, 0, 0.4),
      inset 0 0 0 1px rgba(200, 168, 78, 0.08);
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .content :global(.msg-img img:hover) {
    border-color: rgba(200, 168, 78, 0.5);
    box-shadow:
      0 0 0 1px rgba(0, 0, 0, 0.4),
      0 2px 12px rgba(200, 168, 78, 0.15),
      inset 0 0 0 1px rgba(200, 168, 78, 0.12);
  }
  .content :global(.msg-img figcaption) {
    font-size: 11px;
    color: #9a8a68;
    margin-top: 4px;
    font-style: italic;
    text-align: center;
  }
  .content :global(code) {
    background: rgba(200, 168, 78, 0.08);
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 12px;
    color: #d4c4a0;
  }
  .content :global(pre) {
    background: rgba(0, 0, 0, 0.3);
    padding: 10px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 6px 0;
    border: 1px solid rgba(200, 168, 78, 0.08);
  }
  .content :global(ul), .content :global(ol) {
    padding-left: 18px;
    margin: 4px 0;
  }
  .content :global(p) {
    margin: 4px 0;
  }
  .content :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0;
    font-size: 12px;
  }
  .content :global(th) {
    background: rgba(200, 168, 78, 0.12);
    color: #d4b860;
    font-family: 'Cinzel', serif;
    font-weight: 600;
    padding: 6px 8px;
    border: 1px solid rgba(200, 168, 78, 0.15);
    text-align: left;
  }
  .content :global(td) {
    padding: 5px 8px;
    border: 1px solid rgba(200, 168, 78, 0.1);
  }
  .content :global(tr:nth-child(even)) {
    background: rgba(200, 168, 78, 0.04);
  }
  .content :global(hr) {
    border: none;
    border-top: 1px solid rgba(200, 168, 78, 0.15);
    margin: 8px 0;
  }
  /* ── 아코디언 섹션 ── */
  .content :global(.accordion) {
    border: 1px solid rgba(200, 168, 78, 0.15);
    border-radius: 6px;
    margin: 6px 0;
    background: rgba(200, 168, 78, 0.03);
    overflow: hidden;
  }
  .content :global(.accordion-title) {
    font-family: 'Cinzel', serif;
    font-size: 13px;
    font-weight: 600;
    color: #d4b860;
    padding: 8px 12px;
    cursor: pointer;
    user-select: none;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(200, 168, 78, 0.06);
    border-bottom: 1px solid rgba(200, 168, 78, 0.1);
    transition: background 0.15s;
  }
  .content :global(.accordion-title:hover) {
    background: rgba(200, 168, 78, 0.12);
  }
  /* 화살표 마커 */
  .content :global(.accordion-title::before) {
    content: "▸";
    font-size: 11px;
    color: #c8a84e;
    transition: transform 0.2s;
    flex-shrink: 0;
  }
  .content :global(.accordion[open] > .accordion-title::before) {
    transform: rotate(90deg);
  }
  /* 열렸을 때 하단 보더 제거 */
  .content :global(.accordion:not([open]) > .accordion-title) {
    border-bottom: none;
  }
  .content :global(.accordion-title::-webkit-details-marker) {
    display: none;
  }
  .content :global(.accordion-body) {
    overflow: hidden;
  }
  .content :global(.accordion-body-inner) {
    padding: 6px 12px 10px;
  }

  /* ── WikiLink 미니 팝업 ── */
  .wiki-popup-fixed {
    position: fixed;
    z-index: 200;
    background: rgba(30, 24, 16, 0.97);
    border: 1px solid rgba(200, 168, 78, 0.4);
    border-radius: 8px;
    padding: 10px 12px;
    min-width: 180px;
    max-width: 260px;
    box-shadow:
      0 4px 20px rgba(0, 0, 0, 0.6),
      0 0 8px rgba(200, 168, 78, 0.15),
      inset 0 0 15px rgba(0, 0, 0, 0.3);
    animation: popup-appear 0.2s ease forwards;
  }
  @keyframes popup-appear {
    0% {
      opacity: 0;
      transform: translateY(-4px) scale(0.96);
    }
    100% {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  .wiki-popup-title {
    font-family: 'Cinzel', serif;
    font-size: 13px;
    font-weight: 700;
    color: #f0c050;
    margin-bottom: 8px;
    padding-right: 18px;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  }
  .wiki-popup-actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .wiki-popup-actions button {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 10px;
    border: 1px solid rgba(200, 168, 78, 0.15);
    border-radius: 6px;
    background: rgba(200, 168, 78, 0.06);
    color: #d4c4a0;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .wiki-popup-actions button:hover {
    background: rgba(200, 168, 78, 0.18);
    border-color: rgba(200, 168, 78, 0.35);
    color: #f0dca0;
  }
  .wiki-popup-actions button :global(svg) {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }
  .wiki-popup-close {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: #9a8a68;
    font-size: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .wiki-popup-close:hover {
    color: #f0dca0;
    background: rgba(200, 168, 78, 0.15);
  }
  .actions {
    display: flex;
    gap: 4px;
    margin-top: 6px;
    justify-content: flex-end;
  }
  .actions button {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: rgba(200, 168, 78, 0.06);
    color: #c8a84e;
    font-size: 13px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, color 0.15s;
  }
  .actions button :global(svg) {
    width: 16px;
    height: 16px;
  }
  .actions button:hover {
    background: rgba(200, 168, 78, 0.2);
    color: #f0dca0;
  }
</style>
