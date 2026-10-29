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


# Where a model's completion limit comes from, in order: an explicit HARNESS_MAX_TOKENS
# override, then what the provider advertises, then a conservative fallback that the adaptive
# retry in server.next_budget() corrects in either direction at runtime.
FALLBACK_MAX_TOKENS = 64000

_MODELS_CACHE: tuple[float, str, list[dict[str, Any]]] | None = None
_MODELS_TTL = 300.0
_MODELS_LOCK = threading.Lock()


def _fetch_models(base: str, key: str | None, timeout: float = 20.0) -> list[dict[str, Any]]:
    """The gateway's model entries, including the limits it advertises for each.

    The gateway's /models is slow here (over 5 s), so this is only ever called from a
    background thread or at startup — never on the path that builds an agent.
    """
    if not (base and key):
        return []
    request = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured host
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    return [m for m in (payload.get("data") or []) if isinstance(m, dict)]


_REFRESHING_MODELS = False


def _refresh_models_in_background(base: str, key: str | None) -> None:
    """Fetch model metadata off the hot path; the next run then knows the real limits."""
    global _REFRESHING_MODELS
    with _MODELS_LOCK:
        if _REFRESHING_MODELS:
            return
        _REFRESHING_MODELS = True

    def run() -> None:
        global _MODELS_CACHE, _REFRESHING_MODELS
        try:
            entries = _fetch_models(base, key)
            if entries:
                _MODELS_CACHE = (time.monotonic(), base, entries)
        finally:
            with _MODELS_LOCK:
                _REFRESHING_MODELS = False

    threading.Thread(target=run, name="bifrost-models", daemon=True).start()


def _gateway_models(config: Any) -> list[dict[str, Any]]:
    """Cached gateway model metadata, refreshed in the background so callers never block."""
    base = (getattr(config, "bifrost_base_url", "") or "").rstrip("/")
    if not base:
        return []
    cached = _MODELS_CACHE
    if cached is not None and cached[1] == base and time.monotonic() - cached[0] < _MODELS_TTL:
        return cached[2]
    _refresh_models_in_background(base, getattr(config, "bifrost_api_key", None))
    # Stale data beats no data; an empty cache means the first run falls back and adapts.
    return cached[2] if cached is not None and cached[1] == base else []


def warm_model_limits(config: Any = None) -> None:
    """Start filling the model-metadata cache (call once at service or CLI startup)."""
    cfg = config or _config()
    _gateway_models(cfg)


def output_limit(model: str, config: Any = None) -> int | None:
    """The completion-token limit of ``model``, or ``None`` when nothing advertises one.

    A model alias the gateway does not list (``deepseek-flash-latest``) has no advertised limit;
    callers fall back to ``FALLBACK_MAX_TOKENS`` and let the adaptive retry settle it.
    """
    override = os.environ.get("HARNESS_MAX_TOKENS")
    if override:
        try:
            return int(override)
        except ValueError:
            pass

    if model.startswith(BIFROST_PREFIX):
        wanted = model[len(BIFROST_PREFIX):]
        cfg = config or _config()
        for entry in _gateway_models(cfg):
            names = {
                str(entry.get("id") or ""),
                str(entry.get("normalized_name") or ""),
                str(entry.get("name") or ""),
            }
            if wanted in names or wanted.lower() in {n.lower() for n in names if n}:
                limit = entry.get("max_output_tokens") or entry.get("max_completion_tokens")
                if limit:
                    return int(limit)
        return None

    # Providers pydantic-ai has a profile for (Anthropic, Google, ...).
    try:
        built = resolve(model)
        profile = getattr(built, "profile", None)
        for key in ("max_output_tokens", "max_tokens"):
            value = profile.get(key) if hasattr(profile, "get") else None
            if value:
                return int(value)
    except Exception:
        pass
    return None


def budget_for(model: str, config: Any = None) -> int:
    """The ``max_tokens`` to send: the model's own limit, else a conservative fallback."""
    return output_limit(model, config) or FALLBACK_MAX_TOKENS


def _config() -> Any:
    from kicad_harness import config as config_mod

    return config_mod.get()


def _provider_configured(model: str, config: Any = None) -> bool:
    """Whether the provider behind ``model`` has credentials on this machine.

    Without this a picker offers routes that can only fail — an exhausted OpenRouter key or a
    provider whose key was never set — and choosing one aborts the run.
    """
    if model.startswith(BIFROST_PREFIX):
        if os.environ.get("BIFROST_API_KEY"):
            return True
        return bool(getattr(config, "bifrost_api_key", None))
    provider = model.split(":", 1)[0] if ":" in model else ""
    required = {
        "openai": ("OPENAI_API_KEY",),
        "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "anthropic": ("ANTHROPIC_API_KEY",),
    }.get(provider)
    if not required:
        return True  # unknown provider: let pydantic-ai report it
    return any(os.environ.get(name) for name in required)


def catalog(config) -> list[dict[str, Any]]:
    """Every selectable model, with the id, a label and the provider label."""
    from kicad_harness.config import DEFAULT_MODELS

    ids: list[str] = []
    for model in [config.model, *config.models, *DEFAULT_MODELS]:
        if model and model not in ids and _provider_configured(model, config):
            ids.append(model)
    out = [_entry(model) for model in ids]
    # Bifrost is opt-in: without a base URL the gateway ids are not selectable.
    if (getattr(config, "bifrost_base_url", "") or "").strip():
        seen = {entry["id"] for entry in out}
        for model_id in bifrost_ids(config):
            entry = _entry(BIFROST_PREFIX + model_id)
            if entry["id"] not in seen:
                seen.add(entry["id"])
                out.append(entry)
    # Show the completion limit each model actually gets, so the picker reflects reality.
    for entry in out:
        entry["max_tokens"] = budget_for(entry["id"], config)
    return out


def _entry(model: str) -> dict[str, Any]:
    if model.startswith(BIFROST_PREFIX):
        return {"id": model, "label": model[len(BIFROST_PREFIX):], "provider": "bifrost"}
    provider = model.split(":", 1)[0] if ":" in model else "unknown"
    return {"id": model, "label": model.split(":", 1)[-1], "provider": provider}


# The env var a provider needs before a model on it can run at all.
_PROVIDER_KEY = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def resolve(model: str):
    """Turn a ``bifrost:<id>`` selection into a pydantic-ai model; other routes stay strings."""
    if not model.startswith(BIFROST_PREFIX):
        provider = model.split(":", 1)[0] if ":" in model else ""
        needed = _PROVIDER_KEY.get(provider)
        if needed and not (os.environ.get(needed) or os.environ.get("GOOGLE_API_KEY")):
            raise ValueError(
                f"model {model!r} needs {needed}, which is not set. "
                "Pick a model whose provider is configured, or set the key."
            )
        return model
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from kicad_harness import config as config_mod

    cfg = config_mod.get()
    if not cfg.bifrost_api_key:
        raise ValueError("no Bifrost API key (set BIFROST_API_KEY)")
    provider = OpenAIProvider(base_url=cfg.bifrost_base_url, api_key=cfg.bifrost_api_key)
    return OpenAIChatModel(model[len(BIFROST_PREFIX):], provider=provider)
