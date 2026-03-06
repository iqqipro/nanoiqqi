"""
Model capabilities for hard-gate routing.

Maps OpenRouter (and gateway) model ids to capabilities: tool_calling, vision,
context_length. Used to filter eligible models before scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelCapability:
    """Capabilities of a single model for routing gates.
    Optional AA-sourced fields: pricing (per-request cost), latency (ttft/speed), evaluations (quality).
    """

    model_id: str  # normalized: provider/org/model (e.g. openrouter/anthropic/claude-sonnet-4)
    tool_calling: bool = True
    vision: bool = False
    context_length: int = 128_000
    provider: str = ""  # e.g. "anthropic", "google" for provider-diverse fallback
    cost_tier: str = "mid"  # cheap | mid | frontier (fallback when no per-token pricing)
    # Artificial Analysis–sourced (when available)
    price_per_1m_input: float | None = None
    price_per_1m_output: float | None = None
    ttft_seconds: float | None = None  # median time to first token
    output_tokens_per_second: float | None = None
    evaluations: dict[str, float] | None = None  # e.g. artificial_analysis_intelligence_index, coding_index

    def normalized_id(self) -> str:
        """Return id with consistent openrouter/ prefix for OpenRouter."""
        s = self.model_id.strip().lower()
        if not s.startswith("openrouter/"):
            return f"openrouter/{s}" if s else s
        return s


def _norm(s: str) -> str:
    return s.strip().lower()


def _p(provider: str, slug: str) -> str:
    return f"openrouter/{provider}/{slug}"


# Seed list: common OpenRouter models with plausible capabilities.
# No Haiku-style tiny models; focus on mid/cheap/frontier per provider.
# Extend this list or load from OpenRouter API when available.
OPENROUTER_CAPABILITIES: list[ModelCapability] = [
    # Anthropic (no Haiku)
    ModelCapability(_p("anthropic", "claude-sonnet-4-6"), True, True, 200_000, "anthropic", "mid"),
    ModelCapability(_p("anthropic", "claude-opus-4-6"), True, True, 200_000, "anthropic", "frontier"),
    # Google Gemini
    ModelCapability(_p("google", "gemini-2.0-flash-001"), True, True, 1_000_000, "google", "cheap"),
    ModelCapability(_p("google", "gemini-2.5-flash-lite"), True, True, 1_000_000, "google", "cheap"),
    ModelCapability(_p("google", "gemini-2.5-flash"), True, True, 1_000_000, "google", "mid"),
    ModelCapability(_p("google", "gemini-2.5-pro"), True, True, 1_000_000, "google", "frontier"),
    # OpenAI (5.4, 5.3, mid/cheap)
    ModelCapability(_p("openai", "gpt-4o-mini"), True, True, 128_000, "openai", "cheap"),
    ModelCapability(_p("openai", "gpt-4o"), True, True, 128_000, "openai", "mid"),
    ModelCapability(_p("openai", "gpt-5-nano"), True, True, 128_000, "openai", "cheap"),
    ModelCapability(_p("openai", "gpt-5-mini"), True, True, 128_000, "openai", "mid"),
    ModelCapability(_p("openai", "gpt-5.3"), True, True, 128_000, "openai", "mid"),
    ModelCapability(_p("openai", "gpt-5.3-codex"), True, True, 400_000, "openai", "mid"),
    ModelCapability(_p("openai", "gpt-5.4"), True, True, 1_000_000, "openai", "frontier"),
    # Qwen 3.5 (397B A17B + mid/cheap)
    ModelCapability(_p("qwen", "qwen3.5-flash-02-23"), True, True, 262_144, "qwen", "cheap"),
    ModelCapability(_p("qwen", "qwen3.5-27b"), True, True, 262_144, "qwen", "cheap"),
    ModelCapability(_p("qwen", "qwen3.5-plus-02-15"), True, True, 1_000_000, "qwen", "mid"),
    ModelCapability(_p("qwen", "qwen3.5-122b-a10b-20260224"), True, True, 262_144, "qwen", "mid"),
    ModelCapability(_p("qwen", "qwen3.5-397b-a17b"), True, True, 262_144, "qwen", "frontier"),
    ModelCapability(_p("qwen", "qwen3.5-397b-a17b-20260216"), True, True, 262_144, "qwen", "frontier"),
    # DeepSeek
    ModelCapability(_p("deepseek", "deepseek-chat"), True, False, 64_000, "deepseek", "cheap"),
    ModelCapability(_p("deepseek", "deepseek-v3"), True, False, 64_000, "deepseek", "mid"),
    ModelCapability(_p("deepseek", "deepseek-v3.2"), True, False, 64_000, "deepseek", "mid"),
    # MiniMax
    ModelCapability(_p("minimax", "minimax-m2.5"), True, True, 128_000, "minimax", "mid"),
    # Moonshot Kimi
    ModelCapability(_p("moonshotai", "kimi-k2"), True, True, 131_072, "moonshotai", "cheap"),
    ModelCapability(_p("moonshotai", "kimi-k2.5"), True, True, 262_144, "moonshotai", "mid"),
    # Z-AI GLM
    ModelCapability(_p("z-ai", "glm-4.7-flash"), True, True, 200_000, "z-ai", "cheap"),
    ModelCapability(_p("z-ai", "glm-4.6"), True, True, 200_000, "z-ai", "mid"),
    ModelCapability(_p("z-ai", "glm-5"), True, True, 128_000, "z-ai", "mid"),
    ModelCapability(_p("z-ai", "glm-4.7"), True, True, 200_000, "z-ai", "frontier"),
]

_CAP_BY_ID: dict[str, ModelCapability] = {}
for cap in OPENROUTER_CAPABILITIES:
    n = cap.normalized_id()
    _CAP_BY_ID[n] = cap
    # also without openrouter/ for alias resolution
    short = n.replace("openrouter/", "", 1) if n.startswith("openrouter/") else n
    if short not in _CAP_BY_ID:
        _CAP_BY_ID[short] = cap


def normalize_model_id(model_id: str) -> str:
    """Return openrouter/... form for OpenRouter models."""
    s = _norm(model_id)
    if not s:
        return s
    if s.startswith("openrouter/"):
        return s
    return f"openrouter/{s}"


def get_capability(model_id: str) -> ModelCapability | None:
    """Return capability for a model id (with or without openrouter/ prefix), or None if unknown."""
    s = _norm(model_id)
    if not s:
        return None
    if not s.startswith("openrouter/"):
        s = f"openrouter/{s}"
    cap = _CAP_BY_ID.get(s)
    if cap:
        return cap
    # try by prefix match (e.g. openrouter/anthropic/claude-sonnet-4-20250514 vs claude-sonnet-4)
    for k, v in _CAP_BY_ID.items():
        if s == k or s.startswith(k + "/") or k.startswith(s + "/"):
            return v
    return None


def filter_by_capabilities(
    model_ids: list[str],
    *,
    tools_required: bool = True,
    vision_required: bool = False,
    min_context: int = 0,
) -> list[ModelCapability]:
    """
    Hard gate: keep only models that satisfy the required capabilities.
    model_ids can be aliases or full openrouter/... ids; unknown models are skipped.
    """
    result: list[ModelCapability] = []
    seen = set()
    for mid in model_ids:
        cap = get_capability(mid)
        if not cap or cap.normalized_id() in seen:
            continue
        if tools_required and not cap.tool_calling:
            continue
        if vision_required and not cap.vision:
            continue
        if min_context and cap.context_length < min_context:
            continue
        seen.add(cap.normalized_id())
        result.append(cap)
    return result


def filter_capabilities_list(
    capabilities: list[ModelCapability],
    *,
    tools_required: bool = True,
    vision_required: bool = False,
    min_context: int = 0,
) -> list[ModelCapability]:
    """
    Hard gate: from a list of ModelCapability, keep only those that satisfy requirements.
    Used when the list comes from an external source (e.g. Artificial Analysis API).
    """
    result: list[ModelCapability] = []
    for cap in capabilities:
        if tools_required and not cap.tool_calling:
            continue
        if vision_required and not cap.vision:
            continue
        if min_context and cap.context_length < min_context:
            continue
        result.append(cap)
    return result


def get_eligible_from_capabilities(
    capabilities: list[ModelCapability],
    *,
    tools_required: bool = True,
    vision_required: bool = False,
    min_context: int = 0,
) -> list[str]:
    """Return eligible model ids (normalized) from a capabilities list after hard gates."""
    filtered = filter_capabilities_list(
        capabilities,
        tools_required=tools_required,
        vision_required=vision_required,
        min_context=min_context,
    )
    return [c.normalized_id() for c in filtered]


def get_eligible_model_ids(
    candidate_list: list[str] | None = None,
    *,
    tools_required: bool = True,
    vision_required: bool = False,
    min_context: int = 0,
) -> list[str]:
    """
    Return list of eligible model ids (normalized) after hard gates.
    If candidate_list is None or empty, use built-in OPENROUTER_CAPABILITIES order.
    """
    if candidate_list:
        caps = filter_by_capabilities(
            candidate_list,
            tools_required=tools_required,
            vision_required=vision_required,
            min_context=min_context,
        )
    else:
        caps = filter_by_capabilities(
            [c.model_id for c in OPENROUTER_CAPABILITIES],
            tools_required=tools_required,
            vision_required=vision_required,
            min_context=min_context,
        )
    return [c.normalized_id() for c in caps]


def _has_vision_content(messages: list[dict[str, Any]]) -> bool:
    """Heuristic: check if any message has image content (url or base64)."""
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            continue
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "image_url" or part.get("type") == "image":
                        return True
    return False


def _approx_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count (~4 chars per token)."""
    total = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and "text" in part:
                    total += len(str(part["text"]))
                elif isinstance(part, dict) and "type" in part:
                    total += 100  # placeholder for image
        else:
            total += len(str(c))
    return max(0, total // 4)


def request_requirements(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Derive requirements from the request for hard gates and cost estimation.
    Returns dict with tools_required, vision_required, min_context,
    input_tokens_estimate, output_tokens_estimate.
    """
    tools_required = bool(tools and len(tools) > 0)
    vision_required = _has_vision_content(messages)
    input_est = _approx_tokens(messages)
    output_est = min(max(1024, max_tokens), 8192)
    min_context = input_est + 2048
    return {
        "tools_required": tools_required,
        "vision_required": vision_required,
        "min_context": min_context,
        "input_tokens_estimate": input_est,
        "output_tokens_estimate": output_est,
    }


def estimated_cost_usd(cap: ModelCapability, input_tokens: int, output_tokens: int) -> float | None:
    """
    Estimate cost in USD for this model given input/output token counts.
    Uses price_per_1m_input and price_per_1m_output when available; otherwise returns None.
    """
    if cap.price_per_1m_input is not None and cap.price_per_1m_output is not None:
        return (input_tokens / 1e6) * cap.price_per_1m_input + (output_tokens / 1e6) * cap.price_per_1m_output
    if cap.price_per_1m_input is not None and cap.price_per_1m_output is None:
        return (input_tokens / 1e6) * cap.price_per_1m_input + (output_tokens / 1e6) * cap.price_per_1m_input * 2
    return None


# Keys from AA we use for a single "quality" score (higher = better). Normalize to 0–1 in scoring.
QUALITY_EVAL_KEYS = (
    "artificial_analysis_intelligence_index",
    "artificial_analysis_coding_index",
    "artificial_analysis_math_index",
)

# Agentic Index: primary key for agent/agentic benchmarks; fallback to intelligence index.
# AA Intelligence Index includes an "Agents" category (GDPval-AA, τ²-Bench Telecom).
AGENTIC_INDEX_KEYS = (
    "artificial_analysis_agents_index",
    "artificial_analysis_agentic_index",
    "artificial_analysis_intelligence_index",
)


def agentic_score_from_evaluations(evals: dict[str, float] | None) -> float | None:
    """
    Score for agentic capability from AA evaluations (0–1).
    Uses first available key in AGENTIC_INDEX_KEYS; normalizes to 0–1 (e.g. if AA uses 0–100).
    """
    if not evals:
        return None
    for key in AGENTIC_INDEX_KEYS:
        if key in evals and isinstance(evals[key], (int, float)):
            raw = float(evals[key])
            if raw > 10:
                return min(1.0, raw / 100.0)
            return min(1.0, max(0.0, raw))
    return None


def top_n_capabilities_by_agentic_index(
    capabilities: list[ModelCapability],
    n: int = 15,
) -> list[ModelCapability]:
    """
    Return the top N models by Artificial Analysis Agentic Index (OpenRouter-compatible list).
    Models without an agentic score are ranked last; then by model_id for stability.
    """
    def sort_key(cap: ModelCapability) -> tuple[float, str]:
        score = agentic_score_from_evaluations(cap.evaluations)
        # Higher score first; use -1 so missing scores go last
        return (-(score if score is not None else -1.0), cap.normalized_id())
    sorted_caps = sorted(capabilities, key=sort_key)
    return sorted_caps[:n]


# Domain-specific eval key weights: which AA index to emphasize (rest split evenly).
DOMAIN_EVAL_WEIGHTS: dict[str, tuple[str, ...]] = {
    "code": ("artificial_analysis_coding_index", "artificial_analysis_intelligence_index", "artificial_analysis_math_index"),
    "general": ("artificial_analysis_intelligence_index", "artificial_analysis_coding_index", "artificial_analysis_math_index"),
    "math": ("artificial_analysis_math_index", "artificial_analysis_intelligence_index", "artificial_analysis_coding_index"),
    "agentic": (),  # use agentic_score_from_evaluations instead
}


def _normalize_eval_value(raw: float) -> float:
    """Normalize AA index (often 0–100) to 0–1."""
    if raw > 10:
        return min(1.0, raw / 100.0)
    return min(1.0, max(0.0, raw))


def quality_score_from_evaluations(
    evals: dict[str, float] | None,
    domain: str | None = None,
) -> float | None:
    """
    Aggregate AA evaluations into a single 0–1 quality score.
    If domain is given (code, general, math, agentic), emphasize the relevant index:
    - code: coding_index weighted highest
    - general: intelligence_index weighted highest
    - math: math_index weighted highest
    - agentic: uses agentic_score_from_evaluations
    """
    if not evals:
        return None
    domain = (domain or "").strip().lower() or None
    if domain == "agentic":
        return agentic_score_from_evaluations(evals)
    if domain and domain in DOMAIN_EVAL_WEIGHTS:
        keys = DOMAIN_EVAL_WEIGHTS[domain]
        if keys:
            vals = []
            for i, k in enumerate(keys):
                if k in evals and isinstance(evals[k], (int, float)):
                    raw = float(evals[k])
                    w = 0.6 if i == 0 else 0.2  # first key gets 0.6, others 0.2
                    vals.append((_normalize_eval_value(raw), w))
            if vals:
                total_w = sum(w for _, w in vals)
                return sum(v * w for v, w in vals) / total_w if total_w else None
    # Default: average of all known indices
    vals = [evals[k] for k in QUALITY_EVAL_KEYS if k in evals and isinstance(evals[k], (int, float))]
    if not vals:
        return None
    raw = sum(vals) / len(vals)
    return _normalize_eval_value(raw)


def domain_quality_score(cap: ModelCapability, domain: str | None) -> float:
    """
    Quality score for a model in the given domain (0–1). Used for domain-aware ranking.
    Returns 0.5 if no evaluations or unknown domain.
    """
    if not cap.evaluations:
        return 0.5
    q = quality_score_from_evaluations(cap.evaluations, domain=domain or "general")
    return q if q is not None else 0.5
