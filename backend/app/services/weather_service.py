"""
Weather Intelligence.

Generates a synthetic but physically-plausible weather history, fits a
lightweight per-variable ML forecaster, and produces 24-hour-ahead
predictions. Optionally refreshes from the free Open-Meteo API when
network access is available; silently falls back to the synthetic model
otherwise, since this integration is explicitly optional.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.core import config

_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), config.MODEL_CACHE_DIR)
os.makedirs(_MODEL_DIR, exist_ok=True)

WEATHER_VARIABLES = [
    "temperature_c",
    "humidity_pct",
    "cloud_cover_pct",
    "wind_speed_kmh",
    "solar_irradiance_wm2",
]


def _solar_elevation_factor(hour_of_day: float) -> float:
    """Rough daylight bell curve: 0 at night, peak near solar noon."""
    angle = (hour_of_day - 6.0) / 12.0 * math.pi
    return max(0.0, math.sin(angle))


def generate_synthetic_history(hours: int = config.HISTORY_HOURS, end: Optional[datetime] = None) -> pd.DataFrame:
    """Build `hours` of hourly synthetic weather ending at `end` (default: now)."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    end = end or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    timestamps = [end - timedelta(hours=h) for h in range(hours - 1, -1, -1)]

    rows = []
    for ts in timestamps:
        hour = ts.hour + ts.minute / 60.0
        day_of_year = ts.timetuple().tm_yday
        daylight = _solar_elevation_factor(hour)

        seasonal = 4.0 * math.sin(2 * math.pi * (day_of_year / 365.0))
        base_temp = 24.0 + seasonal + 6.0 * daylight + rng.normal(0, 1.2)
        cloud_cover = float(np.clip(35 + 25 * math.sin(day_of_year / 9.0) + rng.normal(0, 18), 0, 100))
        humidity = float(np.clip(70 - 0.6 * base_temp + 0.25 * cloud_cover + rng.normal(0, 5), 20, 100))
        wind_speed = float(np.clip(8 + 5 * math.sin(hour / 4.0) + rng.normal(0, 2.5), 0, 45))

        clear_sky_irradiance = 1000.0 * daylight
        irradiance = float(
            max(0.0, clear_sky_irradiance * (1 - 0.75 * cloud_cover / 100.0) + rng.normal(0, 15) * daylight)
        )

        rows.append(
            {
                "timestamp": ts,
                "temperature_c": round(base_temp, 2),
                "humidity_pct": round(humidity, 2),
                "cloud_cover_pct": round(cloud_cover, 2),
                "wind_speed_kmh": round(wind_speed, 2),
                "solar_irradiance_wm2": round(irradiance, 2),
            }
        )
    return pd.DataFrame(rows)


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=df.index)
    hour = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
    feats["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    feats["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    doy = df["timestamp"].dt.dayofyear
    feats["doy_sin"] = np.sin(2 * np.pi * doy / 365.0)
    feats["doy_cos"] = np.cos(2 * np.pi * doy / 365.0)
    return feats


def _model_path(variable: str) -> str:
    return os.path.join(_MODEL_DIR, f"weather_{variable}.joblib")


def _get_or_train_model(variable: str, history: pd.DataFrame) -> RandomForestRegressor:
    path = _model_path(variable)
    sample_features = _build_features(history.head(1))
    if os.path.exists(path):
        try:
            model = joblib.load(path)
            # A cached model can load fine (pickle succeeds) but still be
            # unusable -- e.g. it was trained under a different
            # scikit-learn version, or against a different feature set.
            # Actually exercise .predict() once here rather than trusting
            # a bare joblib.load(): that is the only reliable way to catch
            # this class of version-skew failure before it reaches a
            # dashboard request.
            model.predict(sample_features)
            return model
        except Exception:
            pass  # cached file unusable (old sklearn version, corrupt, wrong shape...) -- fall through and retrain

    X = _build_features(history)
    y = history[variable].values
    model = RandomForestRegressor(n_estimators=120, max_depth=8, random_state=config.RANDOM_SEED)
    model.fit(X, y)
    try:
        joblib.dump(model, path)
    except Exception:
        pass  # caching is an optimization -- failing to write it should not break the forecast
    return model


def forecast(history: pd.DataFrame, hours: int = config.FORECAST_HOURS) -> pd.DataFrame:
    """Forecast each weather variable `hours` ahead of the last history timestamp."""
    last_ts = history["timestamp"].max()
    future_ts = [last_ts + timedelta(hours=h) for h in range(1, hours + 1)]
    future_df = pd.DataFrame({"timestamp": future_ts})
    future_feats = _build_features(future_df)

    for variable in WEATHER_VARIABLES:
        model = _get_or_train_model(variable, history)
        preds = model.predict(future_feats)
        if variable in ("cloud_cover_pct", "humidity_pct"):
            preds = np.clip(preds, 0, 100)
        if variable == "solar_irradiance_wm2":
            daylight = future_df["timestamp"].apply(lambda t: _solar_elevation_factor(t.hour + t.minute / 60.0))
            preds = np.where(daylight <= 0.01, 0.0, np.clip(preds, 0, 1100))
        if variable == "wind_speed_kmh":
            preds = np.clip(preds, 0, 60)
        future_df[variable] = np.round(preds, 2)

    return future_df


def solar_impact_factor(cloud_cover_pct: float, irradiance_wm2: float) -> float:
    """
    0-1 multiplier describing how much weather is suppressing solar output
    relative to a clear-sky reference. Used by the energy module.
    """
    clear_sky_reference = 1000.0
    irradiance_factor = float(np.clip(irradiance_wm2 / clear_sky_reference, 0, 1))
    cloud_penalty = float(np.clip(1 - (cloud_cover_pct / 100.0) * 0.15, 0.6, 1.0))
    return round(irradiance_factor * cloud_penalty, 4)


def try_fetch_open_meteo(lat: float = config.SITE_LATITUDE, lon: float = config.SITE_LONGITUDE) -> Optional[pd.DataFrame]:
    """
    Best-effort live weather pull from the free, keyless Open-Meteo API.
    Returns None on any failure so callers fall back to the synthetic
    model -- this integration is optional and never required at startup.
    """
    try:
        import requests

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,shortwave_radiation"
            "&forecast_days=2&timezone=UTC"
        )
        resp = requests.get(url, timeout=4)
        resp.raise_for_status()
        payload = resp.json()["hourly"]
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(payload["time"], utc=True),
                "temperature_c": payload["temperature_2m"],
                "humidity_pct": payload["relative_humidity_2m"],
                "cloud_cover_pct": payload["cloud_cover"],
                "wind_speed_kmh": payload["wind_speed_10m"],
                "solar_irradiance_wm2": payload["shortwave_radiation"],
            }
        )
        return df
    except Exception:
        return None


def get_current_conditions(history: pd.DataFrame) -> dict:
    latest = history.iloc[-1]
    return {
        "timestamp": latest["timestamp"].isoformat(),
        "temperature_c": latest["temperature_c"],
        "humidity_pct": latest["humidity_pct"],
        "cloud_cover_pct": latest["cloud_cover_pct"],
        "wind_speed_kmh": latest["wind_speed_kmh"],
        "solar_irradiance_wm2": latest["solar_irradiance_wm2"],
        "solar_impact_factor": solar_impact_factor(latest["cloud_cover_pct"], latest["solar_irradiance_wm2"]),
    }
