"""
FastAPI server — wraps core/ modules.

Tauri runs this as a sidecar; Svelte frontend calls via HTTP.
"""
from __future__ import annotations

import asyncio

import sys
from pathlib import Path

# Add project root to sys.path (for core/, pipeline/, rag/)
if getattr(sys, "frozen", False):
    _ROOT = Path(sys._MEIPASS)  # PyInstaller bundle
else:
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from core.config import load_config, save_config
from core.logging_setup import setup_logging
from core.providers import PROVIDER_LABELS, PROVIDER_MODELS

setup_logging()

app = FastAPI(title="Grimoire API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ConfigUpdate(BaseModel):
    language: str = ""
    provider: str = ""
    model: str = ""
    api_key: str = ""
    worker_url: str = ""
    timeout_sec: int = 30
    max_tokens: int = 0


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """User message -> LLM response."""
    from core.uesp_agent import chat as uesp_chat

    cfg = load_config()
    reply = await asyncio.to_thread(uesp_chat, req.message, cfg)
    return {"reply": reply}


@app.delete("/history")
async def clear_history():
    """Clear conversation history."""
    from core.uesp_agent import clear_conversation
    clear_conversation()
    return {"status": "cleared"}


@app.get("/config")
async def get_config():
    """Return current config (API keys masked)."""
    cfg = load_config()
    result = {
        "language": cfg.get("language", "en"),
        "provider": cfg.get("provider", "anthropic"),
        "max_tokens": cfg.get("max_tokens", 8192),
        "providers": {},
        "uesp_lookup": cfg.get("uesp_lookup", {}),
    }
    for prov_key in PROVIDER_LABELS:
        prov_cfg = cfg.get(prov_key, {})
        api_key = prov_cfg.get("api_key", "")
        result["providers"][prov_key] = {
            "model": prov_cfg.get("model", ""),
            "api_key_set": bool(api_key),
            "api_key_masked": f"...{api_key[-8:]}" if len(api_key) > 8 else ("***" if api_key else ""),
            "timeout_sec": prov_cfg.get("timeout_sec", 30),
        }
    return result


@app.put("/config")
async def update_config(req: ConfigUpdate):
    """Save settings."""
    cfg = load_config()

    if req.language:
        cfg["language"] = req.language

    if req.provider:
        cfg["provider"] = req.provider
        prov_cfg = cfg.setdefault(req.provider, {})
        if req.model:
            prov_cfg["model"] = req.model
        if req.api_key:
            prov_cfg["api_key"] = req.api_key
        prov_cfg["timeout_sec"] = req.timeout_sec

    if req.max_tokens > 0:
        cfg["max_tokens"] = req.max_tokens

    if req.worker_url is not None:
        uesp = cfg.setdefault("uesp_lookup", {})
        uesp["worker_url"] = req.worker_url
        uesp["enabled"] = bool(req.worker_url)

    save_config(cfg)
    return {"status": "saved"}


@app.get("/providers")
async def get_providers():
    """Provider list + model list."""
    return {
        "labels": PROVIDER_LABELS,
        "models": {k: [{"id": m[0], "name": m[1]} for m in v] for k, v in PROVIDER_MODELS.items()},
    }


@app.get("/db-status")
async def db_status():
    """Check if DB files exist."""
    import os
    from pipeline.db import _db_path
    from pipeline.vector_store import _lance_path
    db_exists = os.path.exists(_db_path())
    lance_exists = os.path.isdir(_lance_path())
    return {
        "uesp_db": db_exists,
        "lore_lance": lance_exists,
        "ready": db_exists,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8111)
