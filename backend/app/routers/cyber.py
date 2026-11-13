"""Cyber Intelligence API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import cyber_service, pipeline

router = APIRouter(prefix="/api/cyber", tags=["cyber"])


def _require_cyber(data: dict) -> None:
    if data["cyber_summary"] is None or data["cyber_events"] is None:
        raise HTTPException(
            status_code=503,
            detail=f"Cyber module unavailable: {data['errors'].get('cyber', 'unknown error')}",
        )


@router.get("/summary")
def summary():
    data = pipeline.get_pipeline()
    _require_cyber(data)
    return data["cyber_summary"]


@router.get("/events")
def events(limit: int = Query(50, ge=1, le=500), only_anomalies: bool = False):
    data = pipeline.get_pipeline()
    _require_cyber(data)
    df = data["cyber_events"]
    if only_anomalies:
        df = df[df["is_anomaly"]]
    df = df.head(limit).copy()
    df["timestamp"] = df["timestamp"].astype(str)
    cols = ["event_id", "timestamp", "asset_id", "risk_score", "is_anomaly", "contributing_factors"] + cyber_service.EVENT_FEATURES
    return {"count": len(df), "events": df[cols].to_dict(orient="records")}


@router.get("/graph")
def graph():
    data = pipeline.get_pipeline()
    if data["asset_graph"] is None:
        raise HTTPException(
            status_code=503,
            detail=f"Cyber module unavailable: {data['errors'].get('cyber', 'unknown error')}",
        )
    return cyber_service.graph_to_json(data["asset_graph"])
