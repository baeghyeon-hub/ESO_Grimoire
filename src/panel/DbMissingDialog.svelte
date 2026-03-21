<script>
  import { getDbStatus } from "../lib/api.js";

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
        alert("Database not found. Please extract the DB files and try again.");
      }
    } catch {
      alert("Backend not responding.");
    }
    checking = false;
  }

  function openDownload() {
    window.open(DB_RELEASE_URL, "_blank");
  }
</script>

<div class="overlay">
  <div class="dialog">
    <h3>Database Required</h3>

    <p class="desc">
      Grimoire needs the ESO database to work. Download <strong>grimoire-db.zip</strong> from the releases page and extract it into the app's <code>db/</code> folder.
    </p>

    <div class="steps">
      <div class="step">
        <span class="num">1</span>
        <span>Download <strong>grimoire-db.zip</strong> from GitHub Releases</span>
      </div>
      <div class="step">
        <span class="num">2</span>
        <span>Press <code>Win+R</code>, type <code>%LOCALAPPDATA%\Grimoire</code> → create a <code>db</code> folder → extract the zip there</span>
      </div>
      <div class="step">
        <span class="num">3</span>
        <span>Click <strong>Re-check</strong> below</span>
      </div>
    </div>

    <div class="buttons">
      <button class="download" onclick={openDownload}>Download DB</button>
      <button class="recheck" onclick={recheck} disabled={checking}>
        {checking ? "Checking..." : "Re-check"}
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
