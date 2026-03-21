<script>
  import { getCurrentWindow, LogicalSize } from "@tauri-apps/api/window";
  import ControlBar from "./ControlBar.svelte";
  import MiniBar from "./MiniBar.svelte";
  import { listen } from "../lib/channel.js";

  let mini = $state(false);

  const BAR_W = 320, BAR_H = 40;
  const MINI_W = 40, MINI_H = 40;

  async function goMini() {
    mini = true;
    try {
      await getCurrentWindow().setSize(new LogicalSize(MINI_W, MINI_H));
    } catch {}
  }

  async function goFull() {
    mini = false;
    try {
      await getCurrentWindow().setSize(new LogicalSize(BAR_W, BAR_H));
    } catch {}
  }

  listen((msg) => {
    if (msg.type === "PANEL_MINIMIZED") {}
  });
</script>

{#if mini}
  <MiniBar onexpand={goFull} />
{:else}
  <ControlBar onmini={goMini} />
{/if}

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }
  :global(html), :global(body), :global(#app) {
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #1a1510;
  }
</style>
