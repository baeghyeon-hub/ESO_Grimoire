<script>
  import { putConfig } from "../lib/api.js";

  let { config = null, providers = null, backendOnline = false, onclose, onrefresh } = $props();

  // Fallback defaults (when backend is offline)
  const FALLBACK_LABELS = {
    anthropic: "Anthropic (Claude)",
    openai: "OpenAI (GPT)",
    google: "Google (Gemini)",
    ollama: "Ollama (Local)",
  };

  const FALLBACK_MODELS = {
    anthropic: [
      { id: "claude-haiku-4-5-20251001", name: "Claude Haiku 4.5" },
      { id: "claude-sonnet-4-20250514", name: "Claude Sonnet 4" },
    ],
    openai: [
      { id: "gpt-4o-mini", name: "GPT-4o Mini" },
      { id: "gpt-4o", name: "GPT-4o" },
      { id: "gpt-4.1-mini", name: "GPT-4.1 Mini" },
      { id: "gpt-4.1-nano", name: "GPT-4.1 Nano" },
    ],
    google: [
      { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash" },
      { id: "gemini-2.5-flash-preview-05-20", name: "Gemini 2.5 Flash" },
      { id: "gemini-3-flash-preview", name: "Gemini 3 Flash" },
    ],
    ollama: [
      { id: "qwen3:8b", name: "Qwen3 8B" },
      { id: "gemma3:12b", name: "Gemma3 12B" },
      { id: "llama3.1:8b", name: "Llama 3.1 8B" },
    ],
  };

  // Actual data to use
  let labels = $derived(providers?.labels || FALLBACK_LABELS);
  let modelMap = $derived(providers?.models || FALLBACK_MODELS);

  // Form state
  const TOKEN_OPTIONS = [
    { value: 4096, label: "Short" },
    { value: 8192, label: "Standard" },
    { value: 16384, label: "Detailed" },
    { value: 32768, label: "Very Detailed" },
  ];

  let selProvider = $state(config?.provider || "google");
  let selModel = $state("");
  let apiKey = $state("");
  let maxTokens = $state(config?.max_tokens || 8192);
  let workerUrl = $state(config?.uesp_lookup?.worker_url || "");
  let timeout = $state(30);

  // Set initial values when config first loads (runs once)
  let configLoaded = $state(false);
  $effect(() => {
    if (config && !configLoaded) {
      configLoaded = true;
      selProvider = config.provider || "google";
      maxTokens = config.max_tokens || 8192;
      workerUrl = config.uesp_lookup?.worker_url || "";

      const provCfg = config.providers?.[selProvider];
      if (provCfg) {
        selModel = provCfg.model || "";
        timeout = provCfg.timeout_sec || 30;
      }
    }
  });

  // Refresh model list when provider changes
  let currentModels = $derived(modelMap[selProvider] || []);

  // Switch to saved model for provider, or first model if none
  let prevProvider = $state("");
  $effect(() => {
    if (selProvider && selProvider !== prevProvider) {
      prevProvider = selProvider;
      // Skip before configLoaded (handled by init effect)
      if (!configLoaded) return;
      const provCfg = config?.providers?.[selProvider];
      selModel = provCfg?.model || currentModels[0]?.id || "";
      timeout = provCfg?.timeout_sec || 30;
    }
  });

  async function handleSave() {
    if (!backendOnline) {
      onclose();
      return;
    }
    try {
      await putConfig({
        provider: selProvider,
        model: selModel,
        api_key: apiKey || "",
        max_tokens: maxTokens,
        worker_url: workerUrl,
        timeout_sec: timeout,
      });
      onrefresh();
      onclose();
    } catch (err) {
      alert("Save failed: " + err.message);
    }
  }

  function handleBackdrop(e) {
    if (e.target === e.currentTarget) onclose();
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="overlay" onclick={handleBackdrop}>
  <div class="dialog">
    <h3>Settings</h3>

    {#if !backendOnline}
      <div class="offline-badge">Backend offline — showing defaults</div>
    {/if}

    <label>
      <span>Provider</span>
      <select bind:value={selProvider}>
        {#each Object.entries(labels) as [key, lbl]}
          <option value={key}>{lbl}</option>
        {/each}
      </select>
    </label>

    <label>
      <span>Model</span>
      <select bind:value={selModel}>
        {#each currentModels as m}
          <option value={m.id}>{m.name}</option>
        {/each}
      </select>
    </label>

    <label>
      <span>Response Length</span>
      <select bind:value={maxTokens}>
        {#each TOKEN_OPTIONS as opt}
          <option value={opt.value}>{opt.label} ({(opt.value / 1024).toFixed(0)}K)</option>
        {/each}
      </select>
    </label>

    <label>
      <span>API Key</span>
      <input
        type="password"
        bind:value={apiKey}
        placeholder={config?.providers?.[selProvider]?.api_key_masked || ""}
      />
    </label>

    <!-- worker_url and timeout_sec are internal settings, hidden from UI -->

    {#if selProvider === "ollama"}
      <div class="warning">
        ⚠ Local models have limited tool-calling ability, which may result in less accurate answers.
        Recommended for personal experimentation or fine-tuned models only.
      </div>
    {/if}

    <div class="buttons">
      <button class="cancel" onclick={onclose}>Cancel</button>
      <button class="save" onclick={handleSave}>Save</button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .dialog {
    background: #221c14;
    border: 1px solid rgba(200, 168, 78, 0.15);
    border-radius: 12px;
    padding: 20px;
    width: 320px;
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  h3 {
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 15px;
    margin: 0;
  }
  .offline-badge {
    background: rgba(224, 165, 85, 0.15);
    border: 1px solid rgba(224, 165, 85, 0.3);
    color: #e0a555;
    font-size: 11px;
    padding: 6px 10px;
    border-radius: 6px;
    text-align: center;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  label span {
    font-size: 11px;
    color: #9a8a68;
    font-weight: 600;
  }
  select, input {
    background: #2a2218;
    border: 1px solid rgba(200, 168, 78, 0.15);
    border-radius: 8px;
    color: #e8dcc8;
    padding: 8px 10px;
    font-size: 13px;
    outline: none;
    font-family: inherit;
  }
  select option {
    background: #2a2218;
    color: #e8dcc8;
  }
  select:focus, input:focus {
    border-color: rgba(200, 168, 78, 0.4);
  }
  .warning {
    background: rgba(200, 120, 40, 0.12);
    border: 1px solid rgba(200, 120, 40, 0.3);
    color: #d4a055;
    font-size: 11px;
    padding: 8px 10px;
    border-radius: 6px;
    line-height: 1.5;
  }
  .buttons {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 4px;
  }
  .buttons button {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .cancel {
    background: rgba(200, 168, 78, 0.08);
    color: #d4c4a0;
  }
  .cancel:hover {
    background: rgba(200, 168, 78, 0.18);
  }
  .save {
    background: #6b5530;
    color: #f0dca0;
  }
  .save:hover {
    background: #7d6438;
  }
</style>
