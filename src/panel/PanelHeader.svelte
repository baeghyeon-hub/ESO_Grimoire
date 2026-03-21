<script>
  import { getCurrentWindow } from "@tauri-apps/api/window";

  let { opacity = 100, onopacity, onsettings, onclear, onminimize } = $props();

  let showSlider = $state(false);

  function startDrag(e) {
    if (e.target.closest("button") || e.target.closest(".slider-wrap")) return;
    getCurrentWindow().startDragging();
  }

  function minimize() {
    onminimize?.();
  }

  async function close() {
    await getCurrentWindow().close();
  }

  function handleOpacity(e) {
    onopacity(Number(e.target.value));
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="header" onmousedown={startDrag}>
  <span class="title">Grimoire</span>
  <div class="actions">
    <button onclick={() => (showSlider = !showSlider)} title="Opacity" class:active={showSlider}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><path d="M12 2V4M12 20V22M4 12H2M22 12H20M5.6 5.6L4.2 4.2M18.4 18.4L19.8 19.8M18.4 5.6L19.8 4.2M5.6 18.4L4.2 19.8"/><path d="M12 7A5 5 0 0 1 12 17" fill="currentColor" opacity="0.3"/></svg>
    </button>
    <button onclick={onsettings} title="Settings">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 1V4M12 20V23M4.2 4.2L6.3 6.3M17.7 17.7L19.8 19.8M1 12H4M20 12H23M4.2 19.8L6.3 17.7M19.8 4.2L17.7 6.3"/></svg>
    </button>
    <button onclick={onclear} title="Clear">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22C8 22 5 18.5 5 15C5 11 8 8 9 5C10 8 12 9 12 9C12 9 11 11 12 13C13 11 14 9 14 9C16 12 19 13 19 16C19 19 16 22 12 22Z"/><path d="M12 22C10.5 22 9 20.5 9 18.5C9 16.5 12 15 12 15C12 15 15 16.5 15 18.5C15 20.5 13.5 22 12 22Z" fill="currentColor" opacity="0.2"/></svg>
    </button>
    <button onclick={minimize} title="Minimize">─</button>
    <button class="close" onclick={close} title="Close">✕</button>
  </div>
</div>

{#if showSlider}
  <div class="slider-wrap">
    <span class="slider-label">Opacity</span>
    <input
      type="range"
      min="20"
      max="100"
      value={opacity}
      oninput={handleOpacity}
      class="opacity-slider"
    />
    <span class="slider-value">{opacity}%</span>
  </div>
{/if}

<style>
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 38px;
    padding: 0 12px;
    background:
      linear-gradient(180deg, rgba(32, 26, 18, var(--bg-alpha, 0.95)) 0%, rgba(24, 20, 14, var(--bg-alpha, 0.9)) 100%);
    border-bottom: 1px solid rgba(200, 168, 78, 0.18);
    cursor: grab;
    user-select: none;
    flex-shrink: 0;
  }
  .title {
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  }
  .actions {
    display: flex;
    gap: 2px;
  }
  button {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #c8a84e;
    font-size: 13px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, color 0.15s;
  }
  button :global(svg) {
    width: 16px;
    height: 16px;
  }
  button:hover {
    background: rgba(200, 168, 78, 0.2);
    color: #f0dca0;
  }
  button.active {
    background: rgba(200, 168, 78, 0.25);
    color: #f0dca0;
  }
  .close:hover {
    background: #c05040;
    color: white;
  }

  .slider-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(24, 20, 14, var(--bg-alpha, 0.9));
    border-bottom: 1px solid rgba(200, 168, 78, 0.12);
    flex-shrink: 0;
  }
  .slider-label {
    font-size: 11px;
    color: #9a8a68;
    white-space: nowrap;
  }
  .slider-value {
    font-size: 11px;
    color: #d4c4a0;
    min-width: 32px;
    text-align: right;
  }
  .opacity-slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: rgba(200, 168, 78, 0.15);
    border-radius: 2px;
    outline: none;
    cursor: pointer;
  }
  .opacity-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #c8a84e;
    cursor: pointer;
    border: none;
  }
</style>
