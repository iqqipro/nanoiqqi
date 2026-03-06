"""
Five-stage routing pipeline for OpenRouter: hard gates, optional judge, score+select,
execute with fallback, outcome learning.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.providers.model_capabilities import (
    ModelCapability,
    estimated_cost_usd,
    get_capability,
    get_eligible_model_ids,
    get_eligible_from_capabilities,
    quality_score_from_evaluations,
    request_requirements,
)
from nanobot.providers.router_metrics import RouterMetrics, DEFAULT_LATENCY_MS

# Judge result: complexity (simple|medium|complex), domain (code|general|math|agentic|unknown)
JUDGE_COMPLEXITY_TO_BONUS = {"simple": 0.0, "medium": 0.2, "complex": 0.4}
JUDGE_DOMAINS = frozenset({"code", "general", "math", "agentic", "unknown"})


def parse_judge_response(text: str) -> dict[str, str]:
    """
    Parse judge LLM response into complexity and domain.
    Accepts: JSON {"complexity":"complex","domain":"code"}, or "complexity: complex, domain: code".
    Returns dict with keys "complexity" (simple|medium|complex) and "domain" (code|general|math|agentic|unknown).
    """
    out = {"complexity": "medium", "domain": "general"}
    if not text or not isinstance(text, str):
        return out
    text = text.strip().lower()
    # Try JSON first
    try:
        # Allow single-line JSON
        data = json.loads(text.strip())
        if isinstance(data, dict):
            c = (data.get("complexity") or "").strip().lower()
            d = (data.get("domain") or "").strip().lower()
            if c in JUDGE_COMPLEXITY_TO_BONUS:
                out["complexity"] = c
            if d in JUDGE_DOMAINS:
                out["domain"] = d
            return out
    except (json.JSONDecodeError, TypeError):
        pass
    # Pattern: complexity: X , domain: Y (order flexible)
    complexity_match = re.search(r"complexity\s*:\s*(\w+)", text)
    domain_match = re.search(r"domain\s*:\s*(\w+)", text)
    if complexity_match:
        c = complexity_match.group(1).lower()
        if c in JUDGE_COMPLEXITY_TO_BONUS:
            out["complexity"] = c
    if domain_match:
        d = domain_match.group(1).lower()
        if d in JUDGE_DOMAINS:
            out["domain"] = d
    # Fallback: legacy one-word reply
    if "complex" in text and "complexity" not in text:
        out["complexity"] = "complex"
    elif "medium" in text:
        out["complexity"] = "medium"
    elif "simple" in text:
        out["complexity"] = "simple"
    return out


def _adjust_weights_for_complexity(
    weights: dict[str, float],
    complexity: str,
) -> dict[str, float]:
    """When task is complex, give more weight to quality/fit and less to cost."""
    w = dict(weights)
    if complexity != "complex":
        return w
    fit = w.get("fit", 0.4) + 0.15
    cost = max(0.0, w.get("cost", 0.2) - 0.15)
    w["fit"] = fit
    w["cost"] = cost
    return w


def _get_weights(
    policy: str,
    config_weights: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    from nanobot.config.schema import DEFAULT_ROUTING_WEIGHTS
    base = DEFAULT_ROUTING_WEIGHTS.get(policy, DEFAULT_ROUTING_WEIGHTS["balanced"])
    overrides = (config_weights or {}).get(policy, {})
    return {**base, **overrides}


def _score_model(
    model_id: str,
    cap: ModelCapability | None,
    weights: dict[str, float],
    metrics: RouterMetrics,
    preferred_model: str | None,
    fit_bonus: float = 0.0,
    request_context: dict[str, Any] | None = None,
    domain: str | None = None,
) -> float:
    """
    Score a model: fit*w_fit + cost*w_cost + latency*w_latency + reliability*w_reliability + structure*w_structure.
    Uses AA data when available. When domain is set (code|general|math|agentic), quality uses the relevant index.
    """
    mid_norm = model_id.strip().lower()
    pref = (preferred_model or "").strip().lower()
    # Fit: prefer default only when request is medium/complex (fit_bonus >= 0.2); else mild preference (0.7)
    if pref and mid_norm == pref:
        fit = 1.0 if fit_bonus >= 0.2 else 0.7
    else:
        fit = 0.5 + fit_bonus
    # Quality: domain-aware so code tasks favor coding index, general favor intelligence, etc.
    quality = quality_score_from_evaluations(cap.evaluations, domain=domain) if cap and cap.evaluations else None
    if quality is not None:
        fit = fit * (0.7 + 0.3 * quality)
    # Cost: per-request estimate when we have AA pricing + token estimates; else cost_tier
    in_tok = (request_context or {}).get("input_tokens_estimate", 0) or 0
    out_tok = (request_context or {}).get("output_tokens_estimate", 1024) or 1024
    cost_usd = estimated_cost_usd(cap, in_tok, out_tok) if cap else None
    if cost_usd is not None and cost_usd >= 0:
        cost_score = 1.0 / (1.0 + 10.0 * cost_usd)
    else:
        cost_tier = (cap.cost_tier if cap else "mid").lower()
        cost_score = {"cheap": 1.0, "mid": 0.6, "frontier": 0.2}.get(cost_tier, 0.6)
    # Latency: use AA ttft when we have no outcome data yet; else EMA
    lat_ms = metrics.get_latency_ema(model_id)
    if lat_ms == DEFAULT_LATENCY_MS and cap and cap.ttft_seconds is not None and cap.ttft_seconds > 0:
        lat_ms = cap.ttft_seconds * 1000.0
    latency_score = 1.0 / (1.0 + lat_ms / 5000.0)
    reliability_score = metrics.get_success_rate(model_id)
    structure_score = 1.0 if (cap and cap.tool_calling) else 0.5
    w = weights
    return (
        w.get("fit", 0.4) * fit
        + w.get("cost", 0.2) * cost_score
        + w.get("latency", 0.15) * latency_score
        + w.get("reliability", 0.2) * reliability_score
        + w.get("structure", 0.05) * structure_score
    )


def _select_primary_and_fallbacks(
    eligible_ids: list[str],
    weights: dict[str, float],
    metrics: RouterMetrics,
    preferred_model: str | None,
    max_fallbacks: int = 3,
    cap_by_id: dict[str, ModelCapability] | None = None,
    request_context: dict[str, Any] | None = None,
    fit_bonus: float = 0.0,
    domain: str | None = None,
) -> tuple[str, list[str]]:
    """Score eligible models, pick primary and provider-diverse fallback chain."""
    if cap_by_id is None:
        cap_by_id = {mid: get_capability(mid) for mid in eligible_ids}
    scored = [
        (
            mid,
            _score_model(
                mid,
                cap_by_id.get(mid),
                weights,
                metrics,
                preferred_model,
                fit_bonus=fit_bonus,
                request_context=request_context,
                domain=domain,
            ),
        )
        for mid in eligible_ids
    ]
    scored.sort(key=lambda x: -x[1])
    if not scored:
        return "", []
    primary = scored[0][0]
    primary_cap = cap_by_id.get(primary)
    primary_provider = (primary_cap.provider if primary_cap else "") or (primary.split("/")[1] if "/" in primary else "")
    fallbacks: list[str] = []
    seen_providers = {primary_provider}
    # Prefer provider-diverse fallbacks
    for mid, _ in scored[1:]:
        if len(fallbacks) >= max_fallbacks:
            break
        cap = cap_by_id.get(mid)
        prov = (cap.provider if cap else "") or (mid.split("/")[1] if "/" in mid else "")
        if prov not in seen_providers:
            fallbacks.append(mid)
            seen_providers.add(prov)
    # Fill remaining with same-provider if needed
    for mid, _ in scored[1:]:
        if len(fallbacks) >= max_fallbacks:
            break
        if mid not in fallbacks:
            fallbacks.append(mid)
    return primary, fallbacks


JUDGE_PROMPT = """Classify this user request for an AI assistant.

Reply with exactly one line in this format (no other text):
complexity: <simple|medium|complex>, domain: <code|general|math|agentic|unknown>

- complexity: simple = quick fact/list/short answer; medium = explanation or multi-step; complex = coding, refactoring, design, debugging, long reasoning.
- domain: code = programming, APIs, tests, refactor; general = chat, summarization, knowledge; math = calculations, proofs; agentic = tools, multi-step plans, real-world tasks; unknown if unclear.

User request:
"""


async def run_judge(
    inner: LLMProvider,
    messages: list[dict[str, Any]],
    judge_model: str,
) -> dict[str, str]:
    """
    Ask the judge LLM to classify the request. Returns dict with "complexity" (simple|medium|complex)
    and "domain" (code|general|math|agentic|unknown). On failure returns default {"complexity": "medium", "domain": "general"}.
    """
    out = {"complexity": "medium", "domain": "general"}
    if not judge_model or not messages:
        return out
    prompt = JUDGE_PROMPT
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                prompt = JUDGE_PROMPT + content[:600]
            break
    try:
        judge_messages = [{"role": "user", "content": prompt[:2000]}]
        resp = await inner.chat(
            messages=judge_messages,
            tools=None,
            model=judge_model.strip(),
            max_tokens=64,
            temperature=0,
        )
        text = (resp.content or "").strip()
        out = parse_judge_response(text)
        logger.debug("Judge result: complexity={}, domain={}", out["complexity"], out["domain"])
    except Exception as e:
        logger.debug("Judge failed: {}", e)
    return out




class SmartRouter(LLMProvider):
    """
    Five-stage routing pipeline around an inner LLM provider:
    1. Hard gates: filter by tool_calling, vision, context_length.
    2. Optional local judge: classify request for fit bonus.
    3. Score + select: policy weights, pick primary and provider-diverse fallbacks.
    4. Execute: call inner with primary; on error try fallbacks.
    5. Outcome learning: record success and latency to RouterMetrics.
    """

    def __init__(
        self,
        inner: LLMProvider,
        policy: str = "balanced",
        candidate_models: list[str] | None = None,
        judge_model: str = "",
        weights_override: dict[str, dict[str, float]] | None = None,
        metrics: RouterMetrics | None = None,
        default_model_hint: str = "",
        capabilities_from_api: list[ModelCapability] | None = None,
        max_cost_per_request_usd: float = 0,
    ):
        super().__init__(api_key=inner.api_key, api_base=inner.api_base)
        self._inner = inner
        self._policy = policy.lower() or "balanced"
        self._candidate_models = candidate_models or []
        self._judge_model = (judge_model or "").strip()
        self._weights_override = weights_override or {}
        self._metrics = metrics or RouterMetrics(None)
        self._default_model_hint = (default_model_hint or "").strip() or inner.get_default_model()
        # When set, use this list (e.g. from Artificial Analysis) instead of static OPENROUTER_CAPABILITIES
        self._capabilities_from_api = list(capabilities_from_api) if capabilities_from_api else None
        self._max_cost_per_request_usd = max_cost_per_request_usd if max_cost_per_request_usd and max_cost_per_request_usd > 0 else 0.0
        # Models that returned 400 "not a valid model ID" from OpenRouter; skip them in future selection
        self._invalid_model_ids: set[str] = set()

    def get_default_model(self) -> str:
        return self._default_model_hint

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        # 1. Request requirements + hard gates + token estimates for cost
        req = request_requirements(messages, tools, max_tokens=max_tokens)
        if self._capabilities_from_api:
            eligible_ids = get_eligible_from_capabilities(
                self._capabilities_from_api,
                tools_required=req["tools_required"],
                vision_required=req["vision_required"],
                min_context=req["min_context"],
            )
            cap_by_id = {c.normalized_id(): c for c in self._capabilities_from_api if c.normalized_id() in eligible_ids}
        else:
            eligible_ids = get_eligible_model_ids(
                self._candidate_models or None,
                tools_required=req["tools_required"],
                vision_required=req["vision_required"],
                min_context=req["min_context"],
            )
            cap_by_id = None
        # Filter by max cost per request when we have pricing and token estimates
        if self._max_cost_per_request_usd > 0 and cap_by_id:
            in_tok = req.get("input_tokens_estimate", 0) or 0
            out_tok = req.get("output_tokens_estimate", 1024) or 1024
            still_eligible = []
            for mid in eligible_ids:
                cap = cap_by_id.get(mid)
                if not cap:
                    still_eligible.append(mid)
                    continue
                cost = estimated_cost_usd(cap, in_tok, out_tok)
                if cost is None or cost <= self._max_cost_per_request_usd:
                    still_eligible.append(mid)
            eligible_ids = still_eligible
            cap_by_id = {k: v for k, v in (cap_by_id or {}).items() if k in eligible_ids}
        request_context = {
            "input_tokens_estimate": req.get("input_tokens_estimate", 0),
            "output_tokens_estimate": req.get("output_tokens_estimate", 1024),
        }
        # Exclude models that previously returned "not a valid model ID" from OpenRouter
        if self._invalid_model_ids:
            eligible_ids = [m for m in eligible_ids if m.lower() not in self._invalid_model_ids]
            if cap_by_id:
                cap_by_id = {k: v for k, v in cap_by_id.items() if k.lower() not in self._invalid_model_ids}
        if not eligible_ids:
            # No eligible model from list: fall back to default behavior (no smart routing)
            logger.warning("Smart router: no eligible models after hard gates, using default")
            return await self._execute_with_model(
                model or self._default_model_hint,
                messages,
                tools,
                max_tokens,
                temperature,
            )

        # 2. Optional judge: complexity + domain (code|general|math|agentic)
        judge_result = {"complexity": "medium", "domain": "general"}
        if self._judge_model:
            judge_result = await run_judge(self._inner, messages, self._judge_model)
        fit_bonus = JUDGE_COMPLEXITY_TO_BONUS.get(judge_result["complexity"], 0.2)
        domain = judge_result.get("domain") or "general"

        # 3. Score + select (weights adjusted for complexity; quality uses domain)
        weights = _get_weights(self._policy, self._weights_override)
        weights = _adjust_weights_for_complexity(weights, judge_result["complexity"])
        preferred = (model or self._default_model_hint or "").strip()
        if preferred:
            pref_norm = preferred.lower()
            if not pref_norm.startswith("openrouter/"):
                pref_norm = f"openrouter/{pref_norm}"
            if pref_norm not in eligible_ids and get_capability(preferred):
                eligible_ids = [pref_norm] + [m for m in eligible_ids if m != pref_norm]
        primary, fallbacks = _select_primary_and_fallbacks(
            eligible_ids,
            weights,
            self._metrics,
            preferred or None,
            max_fallbacks=3,
            cap_by_id=cap_by_id,
            request_context=request_context,
            fit_bonus=fit_bonus,
            domain=domain,
        )
        if not primary:
            return await self._execute_with_model(
                model or self._default_model_hint,
                messages,
                tools,
                max_tokens,
                temperature,
            )

        # 4. Execute with strategy (simple: primary then fallbacks)
        chain = [primary] + fallbacks
        last_response: LLMResponse | None = None
        for i, chosen in enumerate(chain):
            if chosen.lower() in self._invalid_model_ids:
                continue
            t0 = time.perf_counter()
            try:
                last_response = await self._inner.chat(
                    messages=messages,
                    tools=tools,
                    model=chosen,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                err_text = str(e)
                if "not a valid model" in err_text.lower() or "400" in err_text:
                    self._invalid_model_ids.add(chosen.lower())
                    logger.warning("Marking model as invalid (OpenRouter): {}", chosen)
                self._metrics.record_outcome(chosen, False, None)
                logger.warning("Smart router attempt {} failed: {}", chosen, err_text[:120])
                last_response = None
                continue
            latency_ms = (time.perf_counter() - t0) * 1000
            success = last_response.finish_reason != "error"
            self._metrics.record_outcome(chosen, success, latency_ms)
            if not success and last_response.content and "not a valid model" in (last_response.content or "").lower():
                self._invalid_model_ids.add(chosen.lower())
                logger.warning("Marking model as invalid (OpenRouter): {}", chosen)
            if success:
                if i > 0:
                    logger.info("Smart router fallback succeeded: {}", chosen)
                return last_response
            logger.warning("Smart router attempt {} failed: {}", chosen, (last_response.content or "")[:120])
        return last_response or LLMResponse(content="Error: all routed models failed.", finish_reason="error")

    async def _execute_with_model(
        self,
        chosen: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Single execution and outcome recording."""
        t0 = time.perf_counter()
        resp = await self._inner.chat(
            messages=messages,
            tools=tools,
            model=chosen,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        self._metrics.record_outcome(chosen, resp.finish_reason != "error", latency_ms)
        return resp
