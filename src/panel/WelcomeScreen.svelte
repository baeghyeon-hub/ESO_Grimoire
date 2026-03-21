<script>
  import { t } from "../lib/i18n.js";
  let { onchip } = $props();

  const chips = [
    { label: "Medusa Set", query: "Tell me about the Medusa set" },
    { label: "Oakensoul Ring", query: "Tell me about the Oakensoul Ring" },
    { label: "Magsorc Build", query: "Recommend a Magicka Sorcerer PvE build" },
  ];
</script>

<div class="welcome">
  <h2>{t("welcome_title")}</h2>
  <p>{t("welcome_desc")}</p>
  <div class="chips">
    {#each chips as chip}
      <button onclick={() => onchip(chip.query)}>{chip.label}</button>
    {/each}
  </div>
</div>

<style>
  .welcome {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
    gap: 12px;
  }
  h2 {
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 1px;
  }
  p {
    color: #9a8a68;
    font-size: 13px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-top: 12px;
  }
  button {
    padding: 8px 14px;
    border: 1px solid rgba(200, 168, 78, 0.2);
    border-radius: 16px;
    background: rgba(200, 168, 78, 0.06);
    color: #d4c4a0;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  button:hover {
    background: rgba(200, 168, 78, 0.15);
    border-color: rgba(200, 168, 78, 0.35);
    color: #f0dca0;
  }
</style>
