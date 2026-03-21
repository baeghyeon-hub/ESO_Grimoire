<script>
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import { send } from "../lib/channel.js";

  let { onmini } = $props();
  let panelVisible = $state(true);

  async function togglePanel() {
    send("TOGGLE_PANEL");
    panelVisible = !panelVisible;
  }

  async function closeApp() {
    const win = getCurrentWindow();
    await win.close();
  }
</script>

<div class="bar" data-tauri-drag-region>
  <span class="title" data-tauri-drag-region>Grimoire</span>
  <div class="actions">
    <button onclick={togglePanel} title={panelVisible ? "패널 숨기기" : "패널 보기"}>
      {panelVisible ? "▼" : "▲"}
    </button>
    <button onclick={onmini} title="미니 바">─</button>
    <button class="close" onclick={closeApp} title="종료">✕</button>
  </div>
</div>

<style>
  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    height: 100%;
    padding: 0 12px;
    background: linear-gradient(180deg, #201a12 0%, #1a1510 100%);
    border: 1px solid rgba(200, 168, 78, 0.2);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    cursor: grab;
    user-select: none;
  }
  .title {
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    cursor: grab;
  }
  .actions {
    display: flex;
    gap: 4px;
  }
  button {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: rgba(200, 168, 78, 0.08);
    color: #9a8a68;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
  }
  button:hover {
    background: rgba(200, 168, 78, 0.2);
    color: #d4c4a0;
  }
  .close:hover {
    background: #c05040;
    color: white;
  }
</style>
