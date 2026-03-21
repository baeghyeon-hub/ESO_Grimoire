<script>
  import { currentImage } from '../lib/imageStore.js';

  // 이미지 정보 표시 여부
  let showInfo = true;

  // 원본 URL에서 파일명 추출
  function getFilename() {
    if (!$currentImage.url) return '';
    return $currentImage.url.split('/').pop().split('?')[0]; // 쿼리 파라미터 제거
  }

  // 이미지 출처
  function getSource() {
    if ($currentImage.source === 'uesp') return 'UESP Wiki';
    return 'External';
  }

  $: filename = getFilename();
  $: source = getSource();
</script>

<div class="info-panel">
  <div class="info-toggle">
    <button
      class="toggle-btn"
      on:click={() => (showInfo = !showInfo)}
      title={showInfo ? 'Hide info' : 'Show info'}
    >
      {showInfo ? '▼' : '▶'} Info
    </button>
  </div>

  {#if showInfo}
    <div class="info-content">
      {#if $currentImage.title}
        <div class="info-row">
          <span class="info-label">Caption:</span>
          <span class="info-value">{$currentImage.title}</span>
        </div>
      {/if}

      {#if $currentImage.width && $currentImage.height}
        <div class="info-row">
          <span class="info-label">Dimensions:</span>
          <span class="info-value">{$currentImage.width} × {$currentImage.height}px</span>
        </div>
      {/if}

      <div class="info-row">
        <span class="info-label">Source:</span>
        <span class="info-value">{source}</span>
      </div>

      {#if filename}
        <div class="info-row">
          <span class="info-label">File:</span>
          <span class="info-value info-mono">{filename}</span>
        </div>
      {/if}

      {#if $currentImage.url}
        <div class="info-row">
          <span class="info-label">URL:</span>
          <span class="info-value info-mono info-url">{$currentImage.url}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .info-panel {
    padding: 8px 16px;
    background: rgba(20, 16, 10, 0.4);
    border-top: 1px solid rgba(200, 168, 78, 0.12);
    font-size: 12px;
    max-height: 200px;
    overflow-y: auto;
    flex-shrink: 0;
  }

  .info-toggle {
    display: flex;
    align-items: center;
  }

  .toggle-btn {
    background: none;
    border: none;
    color: #c8a84e;
    cursor: pointer;
    padding: 4px 8px;
    font-family: 'Cinzel', serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    transition: color 0.15s;
  }

  .toggle-btn:hover {
    color: #f0dca0;
  }

  .info-content {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .info-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }

  .info-label {
    font-family: 'Cinzel', serif;
    font-weight: 600;
    font-size: 11px;
    color: #c8a84e;
    flex-shrink: 0;
    min-width: 80px;
    letter-spacing: 0.3px;
  }

  .info-value {
    color: #e8dcc8;
    flex: 1;
    word-break: break-all;
    font-size: 11px;
  }

  .info-mono {
    font-family: 'Courier New', monospace;
    font-size: 10px;
    color: #9a8a68;
  }

  .info-url {
    max-height: 60px;
    overflow-y: auto;
    padding: 4px 6px;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(200, 168, 78, 0.08);
    border-radius: 4px;
  }
</style>
