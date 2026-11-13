"""Energy Intelligence API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import pipeline

router = APIRouter(prefix="/api/energy", tags=["energy"])


def _df_records(df):
    out = df.copy()
    out["timestamp"] = out["timestamp"].astype(str)
    return out.to_dict(orient="records")


def _require_energy(data: dict) -> dict:
    if data["energy"] is None:
        # Energy depends on weather, so surface whichever of the two
        # actually failed rather than a generic message.
        detail = data["errors"].get("energy") or data["errors"].get("weather") or "unknown error"
        raise HTTPException(status_code=503, detail=f"Energy module unavailable: {detail}")
    return data["energy"]


@router.get("/status")
def status():
    data = pipeline.get_pipeline()
    energy = _require_energy(data)
    forecast_df = energy["forecast"]
    latest = energy["history"].iloc[-1]
    next_hour = forecast_df.iloc[0]
    return {
        "current": {
            "timestamp": str(latest["timestamp"]),
            "demand_kw": latest["demand_kw"],
            "solar_kw": latest["solar_kw"],
            "net_load_kw": latest["net_load_kw"],
            "surplus_kw": latest["surplus_kw"],
            "grid_import_kw": latest["grid_import_kw"],
            "grid_export_kw": latest["grid_export_kw"],
            "curtailment_risk_kw": latest["curtailment_risk_kw"],
            "renewable_utilization_pct": latest["renewable_utilization_pct"],
            "grid_stress_score": latest["grid_stress_score"],
            "stress_level": latest["stress_level"],
        },
        "next_hour_forecast": {
            "timestamp": str(next_hour["timestamp"]),
            "demand_kw": next_hour["demand_kw"],
            "solar_kw": next_hour["solar_kw"],
            "net_load_kw": next_hour["net_load_kw"],
            "grid_stress_score": next_hour["grid_stress_score"],
        },
        "peak_forecast_stress": float(forecast_df["grid_stress_score"].max()),
        "total_forecast_curtailment_risk_kwh": float(forecast_df["curtailment_risk_kw"].sum()),
        "total_forecast_solar_kwh": float(forecast_df["solar_kw"].sum()),
        "total_forecast_demand_kwh": float(forecast_df["demand_kw"].sum()),
        "average_renewable_utilization_pct": round(float(forecast_df["renewable_utilization_pct"].mean()), 1),
    }


@router.get("/forecast")
def forecast(hours: int = Query(24, ge=1, le=48)):
    data = pipeline.get_pipeline()
    energy = _require_energy(data)
    return {"hours": hours, "forecast": _df_records(energy["forecast"].head(hours))}


@router.get("/history")
def history(hours: int = Query(168, ge=1, le=24 * 14)):
    data = pipeline.get_pipeline()
    energy = _require_energy(data)
    return {"hours": hours, "history": _df_records(energy["history"].tail(hours))}
