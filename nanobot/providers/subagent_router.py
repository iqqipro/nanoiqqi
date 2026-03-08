"""
Subagent router: task-aware cost-benefit model selection for subagents.

DEPRECATED: Subagent routing is now integrated into SmartRouter via the
routing_profile="subagent" parameter. Use a single SmartRouter instance
with subagent_capabilities_from_api and call chat(..., routing_profile="subagent")
for subagent calls. This module is kept for backward compatibility only.
"""
from __future__ import annotations

import warnings

import re
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.providers.model_capabilities import (
    ModelCapability,
    agentic_score_from_evaluations,
    domain_quality_score,
    estimated_cost_usd,
    filter_capabilities_list,
    request_requirements,
)
from nanobot.providers.smart_router import run_judge


def _infer_task_complexity(task_text: str) -> float:
    """
    Infer required capability level from task description (0.0 = simple, 1.0 = complex).
    Used to avoid overpaying for simple tasks and ensure enough power for hard ones.
    """
    if not task_text or not isinstance(task_text, str):
        return 0.3
    text = task_text.strip().lower()
    if not text:
        return 0.3
    # Length heuristic: longer descriptions often mean more involved tasks
    length_factor = min(1.0, len(text) / 800.0) * 0.4  # cap 0.4 from length
    # Keywords that suggest higher complexity (coding, refactor, implement, analyze, etc.)
    complex_keywords = (
        r"\b(implement|refactor|rewrite|design|architecture|debug|fix\s+the\s+bug|"
        r"analyze|review|migrate|integrate|optimize|algorithm|recursive|concurrent|"
        r"write\s+tests|unit\s+test|e2e|parsing|api\s+design)\b"
    )
    medium_keywords = (
        r"\b(create|add|update|fix|change|improve|document|explain|summarize|"
        r"list|find|search|fetch|format|convert)\b"
    )
    if re.search(complex_keywords, text):
        keyword_factor = 0.5
    elif re.search(medium_keywords, text):
        keyword_factor = 0.25
    else:
        keyword_factor = 0.1
    return min(1.0, 0.2 + length_factor + keyword_factor)


# Map judge complexity to 0–1 for min_capability (simple=0.2, medium=0.45, complex=0.7)
JUDGE_COMPLEXITY_TO_MIN_CAP = {"simple": 0.2, "medium": 0.45, "complex": 0.7}


class SubagentRouter(LLMProvider):
    """
    Router for subagent calls: selects an OpenRouter model using AA data
    so that the model has enough agentic capability for the task while
    minimizing cost. When judge_model is set, uses judge for complexity+domain
    and ranks by domain quality (e.g. coding index for code tasks).
    """

    def __init__(
        self,
        inner: LLMProvider,
        capabilities: list[ModelCapability],
        default_model_hint: str = "",
        judge_model: str = "",
    ):
        warnings.warn(
            "SubagentRouter is deprecated; use SmartRouter with routing_profile='subagent' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(api_key=inner.api_key, api_base=inner.api_base)
        self._inner = inner
        self._capabilities = list(capabilities)
        self._default_model_hint = (default_model_hint or "").strip() or inner.get_default_model()
        self._judge_model = (judge_model or "").strip()

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
        req = request_requirements(messages, tools, max_tokens=max_tokens)
        in_tok = req.get("input_tokens_estimate", 0) or 0
        out_tok = req.get("output_tokens_estimate", 1024) or 1024

        task_text = ""
        for m in messages:
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    task_text = content
                break

        # Use judge for complexity + domain when available; else heuristic
        domain = "general"
        if self._judge_model and task_text:
            judge_result = await run_judge(
                self._inner,
                [{"role": "user", "content": task_text[:1500]}],
                self._judge_model,
            )
            domain = judge_result.get("domain") or "general"
            complexity_label = judge_result.get("complexity") or "medium"
            min_capability = JUDGE_COMPLEXITY_TO_MIN_CAP.get(
                complexity_label,
                0.2 + 0.5 * _infer_task_complexity(task_text),
            )
            logger.debug("SubagentRouter judge: complexity={}, domain={}", complexity_label, domain)
        else:
            complexity = _infer_task_complexity(task_text)
            min_capability = 0.2 + 0.5 * complexity

        eligible = filter_capabilities_list(
            self._capabilities,
            tools_required=req["tools_required"],
            vision_required=req["vision_required"],
            min_context=req["min_context"],
        )
        # Keep only models that meet the minimum agentic capability
        capable: list[tuple[ModelCapability, float, float, float]] = []
        for cap in eligible:
            score = agentic_score_from_evaluations(cap.evaluations)
            if score is None:
                score = 0.5
            if score < min_capability:
                continue
            cost = estimated_cost_usd(cap, in_tok, out_tok)
            cost_val = cost if cost is not None else 1.0
            domain_q = domain_quality_score(cap, domain)
            capable.append((cap, score, cost_val, domain_q))

        if not capable:
            # No model met the bar; use default or first eligible
            fallback = model or self._default_model_hint
            logger.debug(
                "SubagentRouter: no model with capability >= {}; using fallback {}",
                min_capability,
                fallback,
            )
            return await self._inner.chat(
                messages=messages,
                tools=tools,
                model=fallback,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        # Sort by cost ascending, then by domain quality descending (cheap + best for domain)
        capable.sort(key=lambda x: (x[2], -x[3]))
        chosen_cap = capable[0][0]
        chosen_id = chosen_cap.normalized_id()
        logger.debug(
            "SubagentRouter: min_cap {:.2f}, domain {}, chosen {} (cost ~{:.4f}, domain_q ~{:.2f})",
            min_capability,
            domain,
            chosen_id,
            capable[0][2],
            capable[0][3],
        )
        return await self._inner.chat(
            messages=messages,
            tools=tools,
            model=chosen_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )
