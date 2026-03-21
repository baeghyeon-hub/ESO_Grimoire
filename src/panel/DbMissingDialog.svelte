<script>
  import { getDbStatus } from "../lib/api.js";
  import { t } from "../lib/i18n.js";

  let { onready } = $props();
  let checking = $state(false);

  const DB_RELEASE_URL = "https://github.com/baeghyeon/Grimoire/releases";

  async function recheck() {
    checking = true;
    try {
      const status = await getDbStatus();
      if (status.ready) {
        onready?.();
      } else {
        alert(t("db_not_found"));
      }
    } catch {
      alert(t("backend_no_response"));
    }
    checking = false;
  }

  function openDownload() {
    window.open(DB_RELEASE_URL, "_blank");
  }
</script>

<div class="overlay">
  <div class="dialog">
    <h3>{t("db_required")}</h3>

    <p class="desc">{t("db_desc")}</p>

    <div class="steps">
      <div class="step">
        <span class="num">1</span>
        <span>{t("db_step1")}</span>
      </div>
      <div class="step">
        <span class="num">2</span>
        <span>{t("db_step2")}</span>
      </div>
      <div class="step">
        <span class="num">3</span>
        <span>{t("db_step3")}</span>
      </div>
    </div>

    <div class="buttons">
      <button class="download" onclick={openDownload}>{t("download_db")}</button>
      <button class="recheck" onclick={recheck} disabled={checking}>
        {checking ? t("checking") : t("recheck")}
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
  }
  .dialog {
    background: #221c14;
    border: 1px solid rgba(200, 168, 78, 0.2);
    border-radius: 12px;
    padding: 24px;
    width: 340px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  h3 {
    color: #c8a84e;
    font-family: 'Cinzel', serif;
    font-size: 16px;
    margin: 0;
    text-align: center;
  }
  .desc {
    color: #b8a888;
    font-size: 12px;
    line-height: 1.6;
    margin: 0;
  }
  .desc code {
    background: rgba(200, 168, 78, 0.1);
    padding: 1px 5px;
    border-radius: 3px;
    color: #c8a84e;
  }
  .steps {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .step {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    color: #d4c4a0;
  }
  .step code {
    background: rgba(200, 168, 78, 0.1);
    padding: 1px 5px;
    border-radius: 3px;
    color: #c8a84e;
  }
  .num {
    background: rgba(200, 168, 78, 0.15);
    color: #c8a84e;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
  }
  .buttons {
    display: flex;
    gap: 8px;
  }
  .buttons button {
    flex: 1;
    padding: 10px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    font-weight: 600;
    transition: background 0.15s;
  }
  .download {
    background: #6b5530;
    color: #f0e6d0;
  }
  .download:hover {
    background: #7d6438;
  }
  .recheck {
    background: rgba(200, 168, 78, 0.1);
    color: #c8a84e;
    border: 1px solid rgba(200, 168, 78, 0.2) !important;
  }
  .recheck:hover {
    background: rgba(200, 168, 78, 0.2);
  }
  .recheck:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
