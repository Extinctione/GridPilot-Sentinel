"""Pydantic request/response models for the battery optimization endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BatteryOptimizeRequest(BaseModel):
    capacity_kwh: float = Field(400.0, gt=0, le=5000)
    max_charge_kw: float = Field(120.0, gt=0, le=2000)
    max_discharge_kw: float = Field(120.0, gt=0, le=2000)
    charge_efficiency: float = Field(0.95, gt=0, le=1)
    discharge_efficiency: float = Field(0.95, gt=0, le=1)
    min_soc_fraction: float = Field(0.1, ge=0, lt=1)
    max_soc_fraction: float = Field(0.95, gt=0, le=1)
    initial_soc_fraction: float = Field(0.5, ge=0, le=1)
