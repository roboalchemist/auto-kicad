"""Model catalog: the local/configured routes plus the user's Bifrost gateway.

Bifrost is OpenAI-compatible, so its models are offered as ``bifrost:<id>`` and resolved to an
``OpenAIChatModel`` pointed at ``config.bifrost_base_url``.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

BIFROST_PREFIX = "bifrost:"

# Model ids the gateway lists that are not chat models (OCR, ASR, embeddings, rerankers, …).
_NON_CHAT = (
    "embed", "bge", "rerank", "ocr", "asr", "tts", "vad", "diar", "detect", "parakeet",
    "pyannote", "florence", "yolo", "javad", "hy-mt", "chandra", "mineru", "omniparser",
    "paddleocr", "pp-ocr", "qwenvoice", "redimnet",
)


# Aliases the gateway accepts without a provider prefix but does not list in /v1/models.
# Extend with BIFROST_MODELS rather than editing this list.
KNOWN_GOOD_ALIASES = ("deepseek-flash-latest",)


# The gateway call is network-bound (~5 s here) and used to block the whole event loop for every
# /api/models request, which stalled the UI on load. Cache it, serve stale entries while a background
# thread refreshes them, and let the server warm it at startup.
_IDS_CACHE: tuple[float, str, list[str]] | None = None
_IDS_TTL = 300.0
_IDS_LOCK = threading.Lock()
_REFRESHING = False


def _fetch_ids(base: str, key: str | None, timeout: float) -> list[str]:
    """Ask the gateway which models exist (one blocking HTTP call)."""
    ids: list[str] = list(KNOWN_GOOD_ALIASES)
    if not (base and key):
        return ids
    request = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured host
            payload = json.loads(response.read().decode("utf-8"))
        for model in payload.get("data") or []:
            model_id = model.get("id") if isinstance(model, dict) else None
            if not model_id or any(bad in model_id.lower() for bad in _NON_CHAT):
                continue
            ids.append(model_id)
    except Exception:
        # The gateway being down must not hide the curated aliases.
        pass
    seen: list[str] = []
    for model_id in ids:
        if model_id not in seen:
            seen.append(model_id)
    return seen


def _store_ids(base: str, ids: list[str]) -> list[str]:
    global _IDS_CACHE
    _IDS_CACHE = (time.monotonic(), base, list(ids))
    return ids


def _refresh_in_background(base: str, key: str | None, timeout: float) -> None:
    """Refresh a stale cache without making the caller wait for the gateway."""
    global _REFRESHING
    with _IDS_LOCK:
        if _REFRESHING:
            return
        _REFRESHING = True

    def work() -> None:
        global _REFRESHING
        try:
            _store_ids(base, _fetch_ids(base, key, timeout))
        finally:
            with _IDS_LOCK:
                _REFRESHING = False

    threading.Thread(target=work, name="bifrost-catalog", daemon=True).start()


def bifrost_ids(config, *, timeout: float = 8.0) -> list[str]:
    """Chat-capable Bifrost model ids: BIFROST_MODELS, else curated aliases + gateway chat models."""
    explicit = list(getattr(config, "bifrost_models", []) or [])
    if explicit:
        return explicit
    base = (getattr(config, "bifrost_base_url", "") or "").rstrip("/")
    key = getattr(config, "bifrost_api_key", None)
    cached = _IDS_CACHE
    if cached is not None and cached[1] == base:
        if time.monotonic() - cached[0] < _IDS_TTL:
            return list(cached[2])
        # Stale: hand back what we have and let a worker thread refresh it.
        _refresh_in_background(base, key, timeout)
        return list(cached[2])
    if not (base and key):
        return _store_ids(base, list(KNOWN_GOOD_ALIASES))
    return _store_ids(base, _fetch_ids(base, key, timeout))


def catalog(config) -> list[dict[str, Any]]:
    """Every selectable model, with the id, a label and the provider label."""
    from kicad_harness.config import DEFAULT_MODELS

    ids: list[str] = []
    for model in [config.model, *config.models, *DEFAULT_MODELS]:
        if model and model not in ids:
            ids.append(model)
    out = [_entry(model) for model in ids]
    # Bifrost is opt-in: without a base URL the gateway ids are not selectable.
    if (getattr(config, "bifrost_base_url", "") or "").strip():
        out += [_entry(BIFROST_PREFIX + model_id) for model_id in bifrost_ids(config)]
    return out


def _entry(model: str) -> dict[str, Any]:
    if model.startswith(BIFROST_PREFIX):
        return {"id": model, "label": model[len(BIFROST_PREFIX):], "provider": "bifrost"}
    provider = model.split(":", 1)[0] if ":" in model else "unknown"
    return {"id": model, "label": model.split(":", 1)[-1], "provider": provider}


def resolve(model: str):
    """Turn a ``bifrost:<id>`` selection into a pydantic-ai model; other routes stay strings."""
    if not model.startswith(BIFROST_PREFIX):
        return model
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from kicad_harness import config as config_mod

    cfg = config_mod.get()
    if not cfg.bifrost_api_key:
        raise ValueError("no Bifrost API key (set BIFROST_API_KEY or ~/.local/share/opencode/bifrost.key)")
    provider = OpenAIProvider(base_url=cfg.bifrost_base_url, api_key=cfg.bifrost_api_key)
    return OpenAIChatModel(model[len(BIFROST_PREFIX):], provider=provider)
