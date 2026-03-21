<script>
  import { currentImage, zoomLevel, isLoading } from '../lib/imageStore.js';

  let containerEl;
  let imgEl;
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let panOffset = { x: 0, y: 0 };

  function handleImageLoad() {
    isLoading.set(false);
  }

  function handleMouseDown(e) {
    if (e.button !== 0 || $zoomLevel <= 1.1) return;
    isDragging = true;
    dragStart = { x: e.clientX, y: e.clientY };
  }

  function handleMouseMove(e) {
    if (!isDragging || !imgEl) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    panOffset.x += dx;
    panOffset.y += dy;
    dragStart = { x: e.clientX, y: e.clientY };
    imgEl.style.transform = `translate(${panOffset.x}px, ${panOffset.y}px) scale(${$zoomLevel})`;
  }

  function handleMouseUp() {
    isDragging = false;
  }

  $: if ($zoomLevel < 1.1) {
    panOffset = { x: 0, y: 0 };
  }
</script>

<svelte:window on:mousemove={handleMouseMove} on:mouseup={handleMouseUp} />

<div class="display-container" bind:this={containerEl}>
  {#if $currentImage.url}
    <div class="image-wrapper">
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <img
        bind:this={imgEl}
        src={$currentImage.url}
        alt={$currentImage.title}
        on:load={handleImageLoad}
        on:error={() => isLoading.set(false)}
        on:mousedown={handleMouseDown}
        style={`transform: translate(${panOffset.x}px, ${panOffset.y}px) scale(${$zoomLevel}); cursor: ${$zoomLevel > 1.1 ? 'grab' : 'default'}`}
        class="viewer-image"
        loading="eager"
      />
    </div>

    {#if $isLoading}
      <div class="loading-indicator">
        <div class="spinner"></div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .display-container {
    flex: 1;
    overflow: hidden;
    position: relative;
    background: rgba(20, 16, 10, 0.6);
  }

  .image-wrapper {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  .viewer-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transform-origin: center;
    transition: transform 0.1s ease-out;
    user-select: none;
    border: 2px solid rgba(200, 168, 78, 0.2);
    box-shadow:
      0 0 0 1px rgba(0, 0, 0, 0.4),
      0 4px 20px rgba(0, 0, 0, 0.5);
  }

  .viewer-image:active {
    cursor: grabbing;
  }

  .loading-indicator {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(200, 168, 78, 0.2);
    border-top-color: #c8a84e;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
