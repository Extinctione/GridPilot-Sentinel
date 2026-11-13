"""Battery Optimization API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.battery import BatteryOptimizeRequest
from app.services import battery_service, pipeline

router = APIRouter(prefix="/api/battery", tags=["battery"])


def _require_battery(data: dict) -> dict:
    if data["battery_result"] is None:
        detail = (
            data["errors"].get("battery")
            or data["errors"].get("energy")
            or data["errors"].get("weather")
            or "unknown error"
        )
        raise HTTPException(status_code=503, detail=f"Battery module unavailable: {detail}")
    return data["battery_result"]


@router.get("/status")
def status():
    data = pipeline.get_pipeline()
    result = _require_battery(data)
    return {
        "status": result["status"],
        "total_cost": result["total_cost"],
        "cost_savings": result["cost_savings"],
        "curtailment_avoided_kwh": result["curtailment_avoided_kwh"],
        "parameters": result["parameters"],
        "soc_pct": result["soc_pct"],
        "initial_soc_kwh": result["initial_soc_kwh"],
        "initial_soc_pct": result["initial_soc_pct"],
        "final_soc_pct": result["final_soc_pct"],
    }


@router.get("/schedule")
def schedule():
    data = pipeline.get_pipeline()
    result = _require_battery(data)
    timestamps = data["energy"]["forecast"]["timestamp"].astype(str).tolist()
    rows = [
        {
            "timestamp": ts,
            "charge_kw": result["charge_kw"][i],
            "discharge_kw": result["discharge_kw"][i],
            "soc_pct": result["soc_pct"][i],
            "grid_import_kw": result["grid_import_kw"][i],
            "grid_export_kw": result["grid_export_kw"][i],
            "curtailed_kw": result["curtailed_kw"][i],
            "baseline_grid_import_kw": result["baseline"]["grid_import_kw"][i],
            "baseline_grid_export_kw": result["baseline"]["grid_export_kw"][i],
            "baseline_curtailed_kw": result["baseline"]["curtailed_kw"][i],
        }
        for i, ts in enumerate(timestamps)
    ]
    return {
        "schedule": rows,
        "total_cost": result["total_cost"],
        "baseline_cost": result["baseline"]["total_cost"],
        "cost_savings": result["cost_savings"],
    }


@router.post("/optimize")
def optimize(overrides: BatteryOptimizeRequest):
    """Re-run the optimizer against the current forecast with caller-supplied battery parameters."""
    data = pipeline.get_pipeline()
    energy = data["energy"]
    if energy is None:
        detail = data["errors"].get("energy") or data["errors"].get("weather") or "unknown error"
        raise HTTPException(status_code=503, detail=f"Battery module unavailable: {detail}")
    net_load_forecast = energy["forecast"]["net_load_kw"].tolist()
    try:
        return battery_service.optimize(
            net_load_forecast,
            capacity_kwh=overrides.capacity_kwh,
            max_charge_kw=overrides.max_charge_kw,
            max_discharge_kw=overrides.max_discharge_kw,
            charge_eff=overrides.charge_efficiency,
            discharge_eff=overrides.discharge_efficiency,
            min_soc_frac=overrides.min_soc_fraction,
            max_soc_frac=overrides.max_soc_fraction,
            initial_soc_frac=overrides.initial_soc_fraction,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clear, user-facing optimizer error instead of a raw 500
        raise HTTPException(status_code=422, detail=f"Optimizer could not solve with these parameters: {exc}") from exc
