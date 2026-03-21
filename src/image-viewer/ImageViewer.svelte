<script>
  import { onMount } from 'svelte';
  import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { currentImage, error, setImage, setImageList, reset } from '../lib/imageStore.js';
  import { t } from '../lib/i18n.js';
  import ImageDisplay from './ImageDisplay.svelte';
  import ImageToolbar from './ImageToolbar.svelte';
  import ImageInfo from './ImageInfo.svelte';

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    const imagesJson = params.get('images');

    if (imagesJson) {
      // 이미지 리스트 모드 (Prev/Next 지원)
      try {
        const images = JSON.parse(imagesJson);
        const index = parseInt(params.get('index') || '0', 10);
        setImageList(images, index);
      } catch (err) {
        console.error('[ImageViewer] Failed to parse images:', err);
      }
    } else {
      // 단일 이미지 모드
      const url = params.get('url');
      if (url) {
        setImage({
          url,
          thumb: params.get('thumb') || url,
          title: params.get('title') || '',
          source: params.get('source') || 'external'
        });
      }
    }
  });

  function closeWindow() {
    try {
      getCurrentWindow().close();
    } catch {
      try { getCurrentWebviewWindow().close(); } catch {}
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') closeWindow();
  }

  // 커스텀 타이틀바 드래그 (버튼 영역 제외)
  async function startDrag(e) {
    if (e.target.closest('.header-controls')) return;
    try {
      const win = getCurrentWebviewWindow();
      await win.startDragging();
    } catch {}
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="viewer-container">
  <!-- 커스텀 타이틀바 (드래그 가능) -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="viewer-header" on:mousedown={startDrag}>
    <div class="header-title">
      {#if $currentImage.title}
        {$currentImage.title}
      {:else}
        {t("image_viewer")}
      {/if}
    </div>
    <div class="header-controls">
      <button class="ctrl-btn close" on:click|stopPropagation={closeWindow} title={t("close_esc")}>✕</button>
    </div>
  </div>

  <div class="ornament"></div>

  <!-- 메인 콘텐츠 -->
  <div class="viewer-content">
    {#if $error}
      <div class="error-message">{$error}</div>
    {:else if $currentImage.url}
      <ImageDisplay />
      <ImageInfo />
    {:else}
      <div class="empty-message">{t("no_image")}</div>
    {/if}
  </div>

  <div class="ornament"></div>

  {#if $currentImage.url}
    <ImageToolbar />
  {/if}
</div>

<style>
  .viewer-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    background-color: rgba(30, 24, 16, 1);
    background-image:
      radial-gradient(ellipse at center, transparent 40%, rgba(0, 0, 0, 0.5) 100%),
      radial-gradient(ellipse at 15% 25%, rgba(70, 55, 30, 0.25) 0%, transparent 50%),
      radial-gradient(ellipse at 75% 55%, rgba(60, 48, 25, 0.22) 0%, transparent 45%),
      url("/textures/parchment-noise.png?v=3"),
      linear-gradient(
        170deg,
        rgba(42, 34, 22, 1) 0%,
        rgba(30, 24, 16, 1) 35%,
        rgba(35, 28, 18, 1) 65%,
        rgba(25, 20, 14, 1) 100%
      );
    border: 2px solid rgba(200, 168, 78, 0.35);
    outline: 1px solid rgba(200, 168, 78, 0.1);
    outline-offset: 2px;
    box-shadow:
      inset 0 0 40px rgba(0, 0, 0, 0.4),
      inset 0 0 2px rgba(200, 168, 78, 0.08),
      0 0 25px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }

  .viewer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    cursor: grab;
    user-select: none;
    flex-shrink: 0;
    -webkit-app-region: drag;
  }

  .viewer-header:active {
    cursor: grabbing;
  }

  .header-title {
    font-family: 'Cinzel', serif;
    font-size: 14px;
    font-weight: 600;
    color: #c8a84e;
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
    flex: 1;
    letter-spacing: 1px;
  }

  .header-controls {
    display: flex;
    gap: 4px;
    -webkit-app-region: no-drag;
  }

  .ctrl-btn {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: rgba(200, 168, 78, 0.06);
    color: #c8a84e;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, color 0.15s;
  }

  .ctrl-btn:hover {
    background: rgba(200, 168, 78, 0.2);
    color: #f0dca0;
  }

  .ctrl-btn.close:hover {
    background: rgba(192, 80, 64, 0.3);
    color: #ff8a80;
  }

  .ornament {
    height: 2px;
    margin: 0 12px;
    flex-shrink: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(200, 169, 110, 0.15) 15%,
      rgba(200, 169, 110, 0.4) 50%,
      rgba(200, 169, 110, 0.15) 85%,
      transparent 100%
    );
    box-shadow: 0 0 4px rgba(200, 169, 110, 0.15);
  }

  .viewer-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }

  .error-message,
  .empty-message {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #9a8a68;
    font-size: 14px;
  }

  .error-message {
    color: #ff6b6b;
  }
</style>
