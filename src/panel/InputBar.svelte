<script>
  let { loading = false, onsend } = $props();
  let text = $state("");

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onsend(trimmed);
    text = "";
  }

  function onKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }
</script>

<div class="input-bar">
  <textarea
    bind:value={text}
    onkeydown={onKeydown}
    placeholder="Search ESO info (e.g. Medusa set, vDSR)"
    rows="1"
    disabled={loading}
  ></textarea>
  <button onclick={submit} disabled={loading || !text.trim()} title="Send">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12H19"/><path d="M13 6L19 12L13 18"/></svg>
  </button>
</div>

<style>
  .input-bar {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 10px 12px;
    background:
      linear-gradient(0deg, rgba(20, 16, 12, var(--bg-alpha, 0.95)) 0%, rgba(24, 20, 14, var(--bg-alpha, 0.9)) 100%);
    border-top: 1px solid rgba(200, 168, 78, 0.18);
    flex-shrink: 0;
  }
  textarea {
    flex: 1;
    resize: none;
    border: 1px solid rgba(200, 168, 78, 0.15);
    border-radius: 10px;
    background: rgba(200, 168, 78, 0.05);
    color: #e8dcc8;
    padding: 8px 12px;
    font-size: 13px;
    font-family: inherit;
    line-height: 1.4;
    max-height: 100px;
    overflow-y: auto;
    outline: none;
    transition: border-color 0.15s;
  }
  textarea:focus {
    border-color: rgba(200, 168, 78, 0.4);
  }
  textarea::placeholder {
    color: #6a5a40;
  }
  button {
    width: 36px;
    height: 36px;
    border: none;
    border-radius: 10px;
    background: #6b5530;
    color: #f0dca0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 0.15s;
  }
  button:hover:not(:disabled) {
    background: #7d6438;
  }
  button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  button :global(svg) {
    width: 18px;
    height: 18px;
  }
</style>
