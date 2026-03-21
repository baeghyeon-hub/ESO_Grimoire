<script>
  import { getCurrentWindow } from "@tauri-apps/api/window";

  let { onexpand } = $props();

  let sx = 0, sy = 0, moved = false;

  function down(e) {
    sx = e.screenX;
    sy = e.screenY;
    moved = false;
  }

  function move(e) {
    if (e.buttons !== 1 || moved) return;
    if (Math.abs(e.screenX - sx) > 3 || Math.abs(e.screenY - sy) > 3) {
      moved = true;
      getCurrentWindow().startDragging();
    }
  }

  function click() {
    if (!moved) onexpand();
  }
</script>

<button class="g-btn"
  onmousedown={down}
  onmousemove={move}
  onclick={click}
>G</button>

<style>
  .g-btn {
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #2a2218 0%, #1a1510 100%);
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 14px;
    font-weight: 700;
    border: 1px solid rgba(200, 168, 78, 0.25);
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .g-btn:hover {
    background: #3a2e1e;
    border-color: rgba(200, 168, 78, 0.4);
  }
</style>
