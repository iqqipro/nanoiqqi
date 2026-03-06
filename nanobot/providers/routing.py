"""Routing provider: alias resolution + automatic fallback on failure."""

from __future__ import annotations

from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse


class RoutingProvider(LLMProvider):
    """
    Wraps an inner LLMProvider to add model alias resolution and
    automatic fallback to alternative models on failure.

    Usage::

        inner = LiteLLMProvider(...)
        provider = RoutingProvider(
            inner,
            aliases={"haiku": "openrouter/anthropic/claude-haiku-4-5", ...},
            fallback_models=["openrouter/anthropic/claude-haiku-4-5", "openrouter/google/gemini-2.5-flash"],
        )
    """

    def __init__(
        self,
        inner: LLMProvider,
        aliases: dict[str, str] | None = None,
        fallback_models: list[str] | None = None,
    ):
        super().__init__(api_key=inner.api_key, api_base=inner.api_base)
        self._inner = inner
        self._aliases = {k.lower(): v for k, v in (aliases or {}).items()}
        self._fallbacks = fallback_models or []

    def resolve_alias(self, model: str) -> str:
        """Resolve a short alias to its full model identifier."""
        return self._aliases.get(model.lower(), model)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        resolved = self.resolve_alias(model) if model else model
        primary = resolved or self._inner.get_default_model()

        response = await self._inner.chat(
            messages=messages,
            tools=tools,
            model=resolved,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if response.finish_reason != "error":
            return response

        logger.warning("Primary model {} failed: {}", primary, (response.content or "")[:120])

        for fallback in self._fallbacks:
            fb_resolved = self.resolve_alias(fallback)
            if fb_resolved == primary:
                continue
            logger.info("Trying fallback model: {}", fb_resolved)
            response = await self._inner.chat(
                messages=messages,
                tools=tools,
                model=fb_resolved,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if response.finish_reason != "error":
                logger.info("Fallback {} succeeded", fb_resolved)
                return response
            logger.warning("Fallback {} also failed: {}", fb_resolved, (response.content or "")[:120])

        return response

    def get_default_model(self) -> str:
        raw = self._inner.get_default_model()
        return self.resolve_alias(raw)
