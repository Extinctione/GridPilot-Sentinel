"""Cross-Domain Intelligence API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import pipeline

router = APIRouter(prefix="/api/correlation", tags=["correlation"])


@router.get("/risks")
def risks():
    data = pipeline.get_pipeline()
    if data["cross_domain"] is None:
        detail = (
            data["errors"].get("correlation_recommendations")
            or data["errors"].get("battery")
            or data["errors"].get("energy")
            or data["errors"].get("cyber")
            or data["errors"].get("weather")
            or "unknown error"
        )
        raise HTTPException(status_code=503, detail=f"Cross-domain correlation unavailable: {detail}")
    return {"findings": data["cross_domain"]}
