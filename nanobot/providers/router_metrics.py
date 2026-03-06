"""
Outcome learning for the smart router: record success/latency per model, EMA-based stats.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

# EMA alpha: higher = more weight to recent samples (0.1 = ~10 samples to converge)
EMA_ALPHA = 0.15
DEFAULT_LATENCY_MS = 3000.0
DEFAULT_SUCCESS_RATE = 0.95


class RouterMetrics:
    """
    Per-model EMA latency and success rate for routing decisions.
    Optionally persists to workspace/.nanobot/router_metrics.json.
    """

    def __init__(self, persist_path: Path | None = None):
        self._persist_path = persist_path
        # model_id -> {"latency_ema": float, "success_ema": float, "n": int}
        self._stats: dict[str, dict[str, Any]] = {}
        if persist_path and persist_path.exists():
            self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self._stats = data.get("models", {})
        except Exception as e:
            logger.warning("Could not load router metrics from {}: {}", self._persist_path, e)

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(
                json.dumps({"models": self._stats}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not save router metrics to {}: {}", self._persist_path, e)

    def record_outcome(
        self,
        model_id: str,
        success: bool,
        latency_ms: float | None = None,
    ) -> None:
        """Record one request outcome for a model. Updates EMA latency and success rate."""
        key = model_id.strip().lower()
        if not key:
            return
        prev = self._stats.get(key, {
            "latency_ema": DEFAULT_LATENCY_MS,
            "success_ema": DEFAULT_SUCCESS_RATE,
            "n": 0,
        })
        n = prev["n"] + 1
        lat = prev["latency_ema"]
        if latency_ms is not None and latency_ms >= 0:
            lat = EMA_ALPHA * latency_ms + (1 - EMA_ALPHA) * lat
        succ = prev["success_ema"]
        succ = EMA_ALPHA * (1.0 if success else 0.0) + (1 - EMA_ALPHA) * succ
        self._stats[key] = {"latency_ema": lat, "success_ema": succ, "n": n}
        self._save()

    def get_latency_ema(self, model_id: str) -> float:
        """Return EMA latency in ms for the model, or default if unknown."""
        key = model_id.strip().lower()
        if not key:
            return DEFAULT_LATENCY_MS
        s = self._stats.get(key, {})
        return float(s.get("latency_ema", DEFAULT_LATENCY_MS))

    def get_success_rate(self, model_id: str) -> float:
        """Return EMA success rate in [0, 1] for the model."""
        key = model_id.strip().lower()
        if not key:
            return DEFAULT_SUCCESS_RATE
        s = self._stats.get(key, {})
        return float(s.get("success_ema", DEFAULT_SUCCESS_RATE))

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Return copy of per-model stats (for debugging)."""
        return dict(self._stats)
