<script>
  import { currentImage, zoomLevel, historyIndex, imageHistory, zoomIn, zoomOut, resetZoom, fitToWindow, previousImage, nextImage } from '../lib/imageStore.js';
  import { open } from '@tauri-apps/plugin-shell';
  import { t } from '../lib/i18n.js';

  async function downloadImage() {
    if (!$currentImage.url) return;
    try { await open($currentImage.url); } catch (err) {
      console.error('Failed to open image:', err);
    }
  }

  function getUESPLink(url) {
    if (!url || !url.includes('uesp.net')) return null;
    const filename = url.split('/').pop();
    return `https://en.uesp.net/wiki/File:${encodeURIComponent(filename)}`;
  }

  function handleFit() {
    const el = document.querySelector('.display-container');
    if (el) {
      fitToWindow(el.clientWidth, el.clientHeight);
    }
  }

  $: uespLink = getUESPLink($currentImage.url);
  $: canPrevious = $historyIndex > 0;
  $: canNext = $historyIndex < $imageHistory.length - 1;
  $: zoomPercent = Math.round($zoomLevel * 100);
</script>

<div class="toolbar">
  <div class="toolbar-left">
    <button class="tool-btn" on:click={previousImage} disabled={!canPrevious} title={t("prev_image")}>
      {t("prev")}
    </button>
    <button class="tool-btn" on:click={nextImage} disabled={!canNext} title={t("next_image")}>
      {t("next")}
    </button>

    <div class="separator"></div>

    <button class="tool-btn" on:click={zoomOut} title={t("zoom_out")}>−</button>
    <span class="zoom-display">{zoomPercent}%</span>
    <button class="tool-btn" on:click={zoomIn} title={t("zoom_in")}>+</button>
    <button class="tool-btn" on:click={resetZoom} title={t("reset_zoom")}>{t("reset")}</button>

    <div class="separator"></div>

    <button class="tool-btn" on:click={handleFit} title={t("fit_window")}>{t("fit")}</button>
  </div>

  <div class="toolbar-right">
    {#if uespLink}
      <button class="tool-btn accent" on:click={() => open(uespLink)} title={t("open_uesp")}>
        UESP
      </button>
    {/if}
    <button class="tool-btn accent" on:click={downloadImage} title={t("download_original")}>
      {t("download")}
    </button>
  </div>
</div>

<style>
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    flex-shrink: 0;
    gap: 8px;
  }

  .toolbar-left,
  .toolbar-right {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .tool-btn {
    background: rgba(200, 168, 78, 0.06);
    border: 1px solid rgba(200, 168, 78, 0.15);
    color: #c8a84e;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-family: 'Cinzel', serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .tool-btn:hover:not(:disabled) {
    background: rgba(200, 168, 78, 0.2);
    border-color: rgba(200, 168, 78, 0.35);
    color: #f0dca0;
  }

  .tool-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .tool-btn.accent {
    border-color: rgba(200, 168, 78, 0.3);
  }

  .tool-btn.accent:hover:not(:disabled) {
    background: rgba(200, 168, 78, 0.25);
    border-color: rgba(200, 168, 78, 0.5);
    color: #f0dca0;
  }

  .zoom-display {
    font-family: 'Cinzel', serif;
    font-size: 11px;
    color: #e8dcc8;
    min-width: 40px;
    text-align: center;
    font-weight: 600;
  }

  .separator {
    width: 1px;
    height: 18px;
    background: rgba(200, 168, 78, 0.2);
    margin: 0 2px;
  }
</style>
