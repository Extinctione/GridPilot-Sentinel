"""Weather Intelligence API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import pipeline, weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


def _df_records(df):
    out = df.copy()
    out["timestamp"] = out["timestamp"].astype(str)
    return out.to_dict(orient="records")


def _require_weather(data: dict) -> None:
    if data["weather_history"] is None or data["weather_forecast"] is None:
        raise HTTPException(
            status_code=503,
            detail=f"Weather module unavailable: {data['errors'].get('weather', 'unknown error')}",
        )


@router.get("/current")
def current_conditions():
    data = pipeline.get_pipeline()
    _require_weather(data)
    return weather_service.get_current_conditions(data["weather_history"])


@router.get("/forecast")
def forecast(hours: int = Query(24, ge=1, le=48)):
    data = pipeline.get_pipeline()
    _require_weather(data)
    return {"hours": hours, "forecast": _df_records(data["weather_forecast"].head(hours))}


@router.get("/history")
def history(hours: int = Query(168, ge=1, le=24 * 14)):
    data = pipeline.get_pipeline()
    _require_weather(data)
    return {"hours": hours, "history": _df_records(data["weather_history"].tail(hours))}


@router.get("/refresh")
def refresh():
    """Force-regenerate the shared simulation (weather, energy, battery and cyber all refresh together)."""
    pipeline.get_pipeline(force_refresh=True)
    return {"status": "refreshed"}
