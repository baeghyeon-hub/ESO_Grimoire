import os
import sys
import json
import copy


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        # Deployed: save config to AppData (Program Files is read-only)
        appdata = os.environ.get("APPDATA", os.path.dirname(sys.executable))
        base = os.path.join(appdata, "Grimoire")
        os.makedirs(base, exist_ok=True)
        return base
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG: dict = {
    "provider": "anthropic",
    "max_tokens": 8192,
    "anthropic": {
        "api_key": "",
        "model": "claude-haiku-4-5-20251001",
        "timeout_sec": 30,
    },
    "openai": {
        "api_key": "",
        "model": "gpt-4o-mini",
        "timeout_sec": 30,
    },
    "google": {
        "api_key": "",
        "model": "gemini-2.0-flash",
        "timeout_sec": 30,
    },
    "ollama": {
        "api_key": "",
        "model": "qwen3:8b",
        "timeout_sec": 60,
    },
    "voyage": {
        "api_key": "",
        "embed_model": "voyage-4",
        "rerank_model": "rerank-2.5",
    },
    "uesp_lookup": {
        "enabled": True,
        "worker_url": "https://empty-cake-ec0euesp-proxy.baeghyeon828.workers.dev/",
        "timeout_sec": 10,
    },
    "window": {
        "output_x": -1,
        "output_y": -1,
        "output_w": 480,
        "output_h": 560,
        "bar_x": -1,
        "bar_y": -1,
        "opacity": 85,
    },
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = copy.deepcopy(DEFAULT_CONFIG)
            for key in ("provider", "max_tokens"):
                if key in data:
                    merged[key] = data[key]
            for section in ("anthropic", "openai", "google", "ollama", "voyage", "uesp_lookup", "window"):
                if section in data and isinstance(data[section], dict):
                    merged[section].update(data[section])
            return merged
        except Exception:
            pass
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
