"""
Artificial Analysis API client for smart routing.

Fetches LLM model data (pricing, speed, benchmarks) from
https://artificialanalysis.ai/api/v2/data/llms/models and maps to ModelCapability
for use by the smart router. Requires an API key (tools.smart_router.api_key).
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger

from nanoiqqi.providers.model_capabilities import ModelCapability, top_n_capabilities_by_agentic_index

# Cache TTL in seconds (AA recommends caching; rate limit 1000/day)
CACHE_TTL = 3600  # 1 hour

# Only keep AA models whose provider exists on OpenRouter (avoids 400 "not a valid model ID").
# AA includes azure, liquidai, ai2, etc. that OpenRouter does not expose with the same ID.
OPENROUTER_PROVIDER_ALLOWLIST: frozenset[str] = frozenset({
    "anthropic", "google", "openai", "deepseek", "minimax", "moonshotai", "z-ai", "qwen",
    "meta", "microsoft", "mistralai", "cohere", "perplexity", "together",
})


def _cost_tier_from_price(price_per_1m: float) -> str:
    """Map blended price per 1M tokens to cheap | mid | frontier."""
    if price_per_1m <= 0.5:
        return "cheap"
    if price_per_1m <= 3.0:
        return "mid"
    return "frontier"


def _openrouter_id(creator_slug: str, model_slug: str) -> str:
    """Build OpenRouter-style model id from AA creator and model slugs."""
    c = (creator_slug or "").strip().lower().replace(" ", "-")
    m = (model_slug or "").strip().lower().replace(" ", "-")
    if not c or not m:
        return ""
    return f"openrouter/{c}/{m}"


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _evaluations_dict(ev: Any) -> dict[str, float] | None:
    """Extract numeric evaluations into a flat dict for scoring."""
    if not isinstance(ev, dict):
        return None
    out: dict[str, float] = {}
    for k, v in ev.items():
        if isinstance(k, str) and isinstance(v, (int, float)):
            out[k] = float(v)
    return out if out else None


def _parse_aa_model(raw: dict[str, Any]) -> ModelCapability | None:
    """Convert one AA API model object to ModelCapability with full pricing, latency, and evaluations."""
    slug = (raw.get("slug") or "").strip()
    creator = raw.get("model_creator") or {}
    creator_slug = (creator.get("slug") or creator.get("name") or "").strip().lower().replace(" ", "-")
    if not slug or not creator_slug:
        return None
    model_id = _openrouter_id(creator_slug, slug)
    if not model_id:
        return None
    pricing = raw.get("pricing") or {}
    price_in = _float_or_none(pricing.get("price_1m_input_tokens"))
    price_out = _float_or_none(pricing.get("price_1m_output_tokens"))
    price_blended = _float_or_none(pricing.get("price_1m_blended_3_to_1"))
    price_for_tier = price_blended or price_in or price_out or 1.0
    cost_tier = _cost_tier_from_price(price_for_tier)
    ttft = _float_or_none(raw.get("median_time_to_first_token_seconds")) or _float_or_none(raw.get("median_time_to_first_answer_token"))
    tps = _float_or_none(raw.get("median_output_tokens_per_second"))
    evals = _evaluations_dict(raw.get("evaluations"))
    return ModelCapability(
        model_id=model_id,
        tool_calling=True,
        vision=False,
        context_length=128_000,
        provider=creator_slug,
        cost_tier=cost_tier,
        price_per_1m_input=price_in,
        price_per_1m_output=price_out,
        ttft_seconds=ttft,
        output_tokens_per_second=tps,
        evaluations=evals,
    )


_cache: list[ModelCapability] = []
_cache_time: float = 0

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_openrouter_model_ids(openrouter_api_key: str | None = None) -> set[str]:
    """
    Fetch the set of valid model IDs from OpenRouter (optional auth).
    Returns normalized ids: openrouter/{id} (e.g. openrouter/google/gemini-2.5-flash).
    On failure returns empty set (caller may skip filtering).
    """
    out: set[str] = set()
    headers = {}
    if openrouter_api_key and openrouter_api_key.strip():
        headers["Authorization"] = f"Bearer {openrouter_api_key.strip()}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(OPENROUTER_MODELS_URL, headers=headers or None)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.debug("OpenRouter models fetch failed: {}", e)
        return out
    raw_list = data.get("data") if isinstance(data, dict) else []
    if not isinstance(raw_list, list):
        return out
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        mid = (item.get("id") or "").strip()
        if not mid:
            continue
        mid = mid.lower()
        if not mid.startswith("openrouter/"):
            mid = f"openrouter/{mid}"
        out.add(mid)
    return out


def fetch_models(
    api_key: str,
    api_base: str = "https://artificialanalysis.ai/api/v2",
    *,
    use_cache: bool = True,
    openrouter_api_key: str | None = None,
) -> list[ModelCapability]:
    """
    Fetch LLM models from Artificial Analysis and return as ModelCapability list.
    Uses in-memory cache for CACHE_TTL seconds. Requires api_key (x-api-key header).
    If openrouter_api_key is set, only returns models that exist on OpenRouter (avoids 400s and delay).
    """
    global _cache, _cache_time
    if not api_key or not api_key.strip():
        return []
    now = time.monotonic()
    if use_cache and _cache and (now - _cache_time) < CACHE_TTL:
        if openrouter_api_key and openrouter_api_key.strip():
            valid = fetch_openrouter_model_ids(openrouter_api_key.strip())
            if valid:
                return [c for c in _cache if c.normalized_id() in valid]
        return list(_cache)
    url = f"{api_base.rstrip('/')}/data/llms/models"
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers={"x-api-key": api_key.strip()})
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Artificial Analysis API error {}: {}", e.response.status_code, e.response.text[:200])
        return list(_cache) if _cache else []
    except Exception as e:
        logger.warning("Artificial Analysis fetch failed: {}", e)
        return list(_cache) if _cache else []
    raw_list = data.get("data") if isinstance(data, dict) else []
    if not isinstance(raw_list, list):
        return list(_cache) if _cache else []
    valid_openrouter_ids: set[str] | None = None
    if openrouter_api_key and openrouter_api_key.strip():
        valid_openrouter_ids = fetch_openrouter_model_ids(openrouter_api_key.strip())
        if valid_openrouter_ids:
            logger.debug("OpenRouter: {} valid model IDs for filtering AA list", len(valid_openrouter_ids))
    out: list[ModelCapability] = []
    seen: set[str] = set()
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        cap = _parse_aa_model(item)
        if not cap or cap.normalized_id() in seen:
            continue
        if cap.provider.lower() not in OPENROUTER_PROVIDER_ALLOWLIST:
            continue
        if valid_openrouter_ids is not None and cap.normalized_id() not in valid_openrouter_ids:
            continue
        seen.add(cap.normalized_id())
        out.append(cap)
    if out:
        _cache = out
        _cache_time = now
        logger.debug("Artificial Analysis: loaded {} models for smart router", len(out))
    return out


def fetch_top_agentic_models(
    api_key: str,
    api_base: str = "https://artificialanalysis.ai/api/v2",
    *,
    top_n: int = 15,
    use_cache: bool = True,
    openrouter_api_key: str | None = None,
) -> list[ModelCapability]:
    """
    Fetch AA models, keep only those compatible with OpenRouter, and return the top N
    by Artificial Analysis Agentic Index. Use this for the main smart router (top 15 only).
    """
    all_caps = fetch_models(
        api_key,
        api_base,
        use_cache=use_cache,
        openrouter_api_key=openrouter_api_key,
    )
    if top_n <= 0:
        return all_caps
    top = top_n_capabilities_by_agentic_index(all_caps, n=top_n)
    if top and len(top) < len(all_caps):
        logger.debug("Smart router: using top {} models by AA Agentic Index (from {} AA models)", len(top), len(all_caps))
    return top


def clear_cache() -> None:
    """Clear the in-memory model cache (e.g. for tests)."""
    global _cache, _cache_time
    _cache = []
    _cache_time = 0
