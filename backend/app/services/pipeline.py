"""
Shared simulation pipeline.

Every router reads from this module so weather, energy, battery and
cyber data stay consistent with one another within a refresh cycle,
instead of each endpoint generating its own unrelated random world.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from app.core import config
from app.services import (
    battery_service,
    correlation_service,
    cyber_service,
    energy_service,
    recommendation_service,
    weather_service,
)

logger = logging.getLogger("gridpilot")

_cache: Dict[str, Any] = {"built_at": 0.0, "data": None}


def _build() -> dict:
    """
    Build every module's data for one refresh cycle.

    Each domain is wrapped in its own try/except so that one module
    failing (a bad cached model, a solver error, etc.) does not take
    the entire dashboard down with it. Any failure is recorded in
    `errors` under the module name that failed, with the real
    exception message -- routers surface this to the frontend instead
    of hiding it, and modules that do not depend on the failed one
    keep working normally.
    """
    errors: Dict[str, str] = {}

    weather_history = weather_forecast = None
    try:
        weather_history = weather_service.generate_synthetic_history()
        weather_forecast = weather_service.forecast(weather_history)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate this module's failure
        logger.exception("weather module failed to build")
        errors["weather"] = f"{type(exc).__name__}: {exc}"

    energy = None
    if weather_history is not None and weather_forecast is not None:
        try:
            energy = energy_service.build_energy_snapshot(weather_history, weather_forecast)
        except Exception as exc:  # noqa: BLE001
            logger.exception("energy module failed to build")
            errors["energy"] = f"{type(exc).__name__}: {exc}"

    battery_result = None
    if energy is not None:
        try:
            net_load_forecast = energy["forecast"]["net_load_kw"].tolist()
            battery_result = battery_service.optimize(net_load_forecast)
        except Exception as exc:  # noqa: BLE001
            logger.exception("battery module failed to build")
            errors["battery"] = f"{type(exc).__name__}: {exc}"

    scored_events = asset_graph = cyber_summary = None
    try:
        cyber_events = cyber_service.generate_synthetic_events()
        scored_events = cyber_service.detect_anomalies(cyber_events)
        asset_graph = cyber_service.build_asset_graph(scored_events)
        cyber_summary = cyber_service.summarize(scored_events)
    except Exception as exc:  # noqa: BLE001 - cyber is independent of weather/energy/battery
        logger.exception("cyber module failed to build")
        errors["cyber"] = f"{type(exc).__name__}: {exc}"

    cross_domain = recommendations = None
    if energy is not None and battery_result is not None and cyber_summary is not None:
        try:
            cross_domain = correlation_service.find_cross_domain_risks(
                energy["forecast"], battery_result, cyber_summary, scored_events
            )
            recommendations = recommendation_service.build_recommendations(
                energy["forecast"], battery_result, cyber_summary, cross_domain
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("correlation/recommendations module failed to build")
            errors["correlation_recommendations"] = f"{type(exc).__name__}: {exc}"

    return {
        "weather_history": weather_history,
        "weather_forecast": weather_forecast,
        "energy": energy,
        "battery_result": battery_result,
        "cyber_events": scored_events,
        "asset_graph": asset_graph,
        "cyber_summary": cyber_summary,
        "cross_domain": cross_domain,
        "recommendations": recommendations,
        "errors": errors,
    }


def get_pipeline(force_refresh: bool = False) -> dict:
    age = time.time() - _cache["built_at"]
    if force_refresh or _cache["data"] is None or age > config.PIPELINE_REFRESH_SECONDS:
        _cache["data"] = _build()
        _cache["built_at"] = time.time()
    return _cache["data"]
