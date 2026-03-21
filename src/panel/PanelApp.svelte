<script>
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
  import { listen as tauriListen } from "@tauri-apps/api/event";
  import { health, getConfig, getProviders, sendChat, clearHistory, getDbStatus } from "../lib/api.js";
  import { load, save } from "../lib/storage.js";
  import PanelHeader from "./PanelHeader.svelte";
  import ChatList from "./ChatList.svelte";
  import InputBar from "./InputBar.svelte";
  import WelcomeScreen from "./WelcomeScreen.svelte";
  import SettingsDialog from "./SettingsDialog.svelte";
  import DbMissingDialog from "./DbMissingDialog.svelte";

  let messages = $state(load("messages", []));
  let config = $state(null);
  let providers = $state(null);
  let loading = $state(false);
  let showSettings = $state(false);
  let showDbMissing = $state(false);
  let backendOnline = $state(false);
  let opacity = $state(load("panelOpacity", 90));
  let opening = $state(true);
  const MINI_W = 120, MINI_H = 36;
  let lastMiniPos = $state(load("miniPos", null)); // { x, y }

  // Remove opening class after animation completes
  $effect(() => {
    if (opening) {
      const timer = setTimeout(() => (opening = false), 800);
      return () => clearTimeout(timer);
    }
  });

  // Save messages to localStorage on change
  $effect(() => {
    save("messages", messages);
  });

  // Save opacity on change
  $effect(() => {
    save("panelOpacity", opacity);
  });

  // Initial loading
  $effect(() => {
    init();
  });

  async function init() {
    // sidecar 시작 대기 (PyInstaller onefile은 압축 해제에 1-2초 소요)
    for (let attempt = 0; attempt < 15; attempt++) {
      try {
        await health();
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    try {
      const [cfgRes, provRes] = await Promise.all([
        getConfig(),
        getProviders(),
      ]);
      config = cfgRes;
      providers = provRes;
      backendOnline = true;

      // Check if DB exists
      try {
        const dbStatus = await getDbStatus();
        if (!dbStatus.ready) showDbMissing = true;
      } catch { /* ignore if endpoint doesn't exist */ }
    } catch {
      backendOnline = false;
    }
  }

  // Mini mode: hide panel and create separate mini window
  async function goMini() {
    try {
      const panel = getCurrentWindow();
      // hide 전에 패널 위치 가져오기
      const pos = await panel.outerPosition();
      const sf = await panel.scaleFactor() || 1;
      await panel.hide();
      const panelX = Math.round(pos.x / sf);
      const panelY = Math.round(pos.y / sf);

      // 저장된 미니바 위치가 있으면 사용, 아니면 패널 위치
      let startX = panelX, startY = panelY;
      if (lastMiniPos && typeof lastMiniPos.x === "number" && typeof lastMiniPos.y === "number") {
        startX = lastMiniPos.x;
        startY = lastMiniPos.y;
      }

      // 화면 안으로 클램핑 (availWidth/Height = 작업표시줄 제외)
      const sw = window.screen.availWidth || window.screen.width;
      const sh = window.screen.availHeight || window.screen.height;
      startX = Math.max(0, Math.min(startX, sw - MINI_W));
      startY = Math.max(0, Math.min(startY, sh - MINI_H));

      // 미니 윈도우 동적 생성
      const mini = new WebviewWindow("mini", {
        url: "/mini.html",
        width: MINI_W,
        height: MINI_H,
        resizable: false,
        decorations: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        x: startX,
        y: startY,
      });
      // 에러 핸들링
      mini.once("tauri://error", (e) => console.error("mini window error:", e));
    } catch (e) { console.error("goMini error:", e); }
  }

  // 미니 윈도우 클릭 → 패널 복원
  tauriListen("grimoire_ipc", async (event) => {
    if (event.payload?.type === "RESTORE_PANEL") {
      try {
        // 패널에서 직접 미니 윈도우 위치를 읽어서 저장 (IPC보다 확실)
        const miniWin = await WebviewWindow.getByLabel("mini");
        if (miniWin) {
          try {
            const miniPos = await miniWin.outerPosition();
            const sf = await miniWin.scaleFactor() || 1;
            const lx = Math.round(miniPos.x / sf);
            const ly = Math.round(miniPos.y / sf);
            // 유효한 좌표만 저장 (극단값 필터)
            if (Number.isFinite(lx) && Number.isFinite(ly) && Math.abs(lx) < 10000 && Math.abs(ly) < 10000) {
              lastMiniPos = { x: lx, y: ly };
              save("miniPos", lastMiniPos);
            }
          } catch (posErr) { console.warn("failed to read mini position:", posErr); }
          await miniWin.close();
        }
      } catch (e) { console.error("close mini error:", e); }
      // 패널 표시
      const panel = getCurrentWindow();
      await panel.show();
      await panel.setFocus();
      opening = true;
    }
  });

  function handleSend(text) {
    messages = [...messages, { role: "user", content: text }];
    doChat(text);
  }

  async function doChat(text) {
    loading = true;
    try {
      const res = await sendChat(text);
      messages = [...messages, { role: "assistant", content: res.reply }];
    } catch (err) {
      if (err.message.includes("400")) {
        try {
          await clearHistory();
          const res = await sendChat(text);
          messages = [...messages, { role: "assistant", content: res.reply }];
        } catch (retryErr) {
          messages = [...messages, { role: "assistant", content: `Error: ${retryErr.message}` }];
        }
      } else {
        messages = [...messages, { role: "assistant", content: `Error: ${err.message}` }];
      }
    }
    loading = false;
  }

  async function handleClear() {
    try {
      await clearHistory();
    } catch {}
    messages = [];
  }

  function handleChip(query) {
    handleSend(query);
  }

  // WikiLink popup "Ask Grimoire" click
  function handleWikiSearch(e) {
    handleSend(`Tell me about ${e.detail}`);
  }

  // DOM 이벤트 리스너 (CustomEvent bubbling)
  $effect(() => {
    document.addEventListener("wikisearch", handleWikiSearch);
    return () => document.removeEventListener("wikisearch", handleWikiSearch);
  });

</script>

<div class="panel" class:opening style="--bg-alpha: {opacity / 100}">
    <!-- 두루마리 펼침 시 골드 빛 갈라짐 -->
    {#if opening}
      <div class="scroll-seam"></div>
    {/if}
    <div class="scroll-overlay" class:opening></div>
    <PanelHeader
      {opacity}
      onopacity={(v) => (opacity = v)}
      onsettings={() => (showSettings = true)}
      onclear={handleClear}
      onminimize={goMini}
    />

    <div class="ornament"></div>

    {#if messages.length === 0}
      <WelcomeScreen onchip={handleChip} />
    {:else}
      <ChatList {messages} {loading} />
    {/if}

    <div class="ornament"></div>

    <InputBar {loading} onsend={handleSend} />

    {#if showSettings}
      <SettingsDialog
        {config}
        {providers}
        {backendOnline}
        onclose={() => (showSettings = false)}
        onrefresh={init}
      />
    {/if}

    {#if showDbMissing}
      <DbMissingDialog onready={() => (showDbMissing = false)} />
    {/if}
  </div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    height: 100vh;
    position: relative;
    background-color: rgba(30, 24, 16, var(--bg-alpha, 0.9));
    background-image:
      /* 비네팅 */
      radial-gradient(ellipse at center, transparent 40%, rgba(0, 0, 0, 0.5) 100%),
      /* 양피지 얼룩 */
      radial-gradient(ellipse at 15% 25%, rgba(70, 55, 30, 0.25) 0%, transparent 50%),
      radial-gradient(ellipse at 75% 55%, rgba(60, 48, 25, 0.22) 0%, transparent 45%),
      radial-gradient(ellipse at 35% 80%, rgba(65, 50, 28, 0.2) 0%, transparent 40%),
      radial-gradient(ellipse at 85% 15%, rgba(55, 42, 22, 0.18) 0%, transparent 35%),
      /* 타일링 노이즈 텍스처 (양피지 질감) */
      url("/textures/parchment-noise.png?v=3"),
      /* 베이스 그라데이션 */
      linear-gradient(
        170deg,
        rgba(42, 34, 22, var(--bg-alpha, 0.9)) 0%,
        rgba(30, 24, 16, var(--bg-alpha, 0.9)) 35%,
        rgba(35, 28, 18, var(--bg-alpha, 0.9)) 65%,
        rgba(25, 20, 14, var(--bg-alpha, 0.9)) 100%
      );
    /* 이중 골드 테두리 */
    border: 2px solid rgba(200, 168, 78, 0.35);
    outline: 1px solid rgba(200, 168, 78, 0.1);
    outline-offset: 2px;
    box-shadow:
      inset 0 0 40px rgba(0, 0, 0, 0.4),
      inset 0 0 2px rgba(200, 168, 78, 0.08),
      0 0 25px rgba(0, 0, 0, 0.6);
  }

  /* ── 두루마리 펼침 애니메이션 (GPU 가속) ── */

  /* 패널 자체: 페이드인 + 살짝 확대 */
  .panel.opening {
    animation: panel-appear 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    will-change: transform, opacity;
  }
  @keyframes panel-appear {
    0% {
      opacity: 0;
      transform: scale(0.97) translateY(-8px);
    }
    100% {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }

  /* 검은 오버레이가 위→아래로 걷히는 효과 (두루마리 느낌) */
  .scroll-overlay {
    position: absolute;
    inset: 0;
    z-index: 50;
    pointer-events: none;
    background: linear-gradient(
      to bottom,
      transparent 0%,
      rgba(18, 14, 8, 1) 2%,
      rgba(18, 14, 8, 1) 100%
    );
    transform: translateY(0);
    opacity: 0;
    will-change: transform, opacity;
  }
  .scroll-overlay.opening {
    animation: overlay-reveal 0.65s cubic-bezier(0.25, 1, 0.5, 1) forwards;
  }
  @keyframes overlay-reveal {
    0% {
      opacity: 1;
      transform: translateY(0);
    }
    100% {
      opacity: 0;
      transform: translateY(100%);
    }
  }

  /* 골드 빛 경계선 — 오버레이 상단에 붙어서 같이 내려감 */
  .scroll-seam {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 2px;
    z-index: 51;
    pointer-events: none;
    background: linear-gradient(
      90deg,
      transparent 5%,
      rgba(240, 200, 80, 0.6) 25%,
      rgba(255, 220, 100, 0.85) 50%,
      rgba(240, 200, 80, 0.6) 75%,
      transparent 95%
    );
    box-shadow:
      0 0 10px rgba(240, 200, 80, 0.5),
      0 0 25px rgba(200, 168, 78, 0.25);
    will-change: transform, opacity;
    animation: seam-sweep 0.65s cubic-bezier(0.25, 1, 0.5, 1) forwards;
  }
  @keyframes seam-sweep {
    0% {
      transform: translateY(0);
      opacity: 0;
    }
    8% {
      opacity: 1;
    }
    75% {
      opacity: 0.7;
    }
    100% {
      transform: translateY(100vh);
      opacity: 0;
    }
  }

  .ornament {
    height: 2px;
    margin: 2px 12px;
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
</style>
