"""
Energy Intelligence.

Forecasts demand and solar generation, computes net load, flags
renewable surplus / curtailment risk, and produces a 0-100 grid-stress
score. Solar generation is derived from the weather module's output
rather than from an independent, disconnected assumption.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.core import config
from app.services import weather_service


def _demand_shape(hour: float) -> float:
    """Normalized (roughly 0-1) daily demand shape: morning + evening peaks."""
    morning = 0.55 * math.exp(-((hour - 8.5) ** 2) / (2 * 2.2**2))
    evening = 1.0 * math.exp(-((hour - 19.5) ** 2) / (2 * 2.6**2))
    base = 0.35
    return base + morning + evening


def generate_synthetic_demand_history(weather_history: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(config.RANDOM_SEED + 1)
    rows = []
    for _, w in weather_history.iterrows():
        ts = w["timestamp"]
        hour = ts.hour + ts.minute / 60.0
        shape = _demand_shape(hour)
        weekday_factor = 1.0 if ts.weekday() < 5 else 0.85
        cooling_load = max(0.0, (w["temperature_c"] - 26.0)) * 6.0
        demand_kw = config.PEAK_DEMAND_KW * shape * weekday_factor + cooling_load + rng.normal(0, 8)
        rows.append({"timestamp": ts, "demand_kw": round(max(40.0, demand_kw), 2)})
    return pd.DataFrame(rows)


def _solar_output_kw(weather_row) -> float:
    factor = weather_service.solar_impact_factor(weather_row["cloud_cover_pct"], weather_row["solar_irradiance_wm2"])
    return round(max(0.0, config.SOLAR_CAPACITY_KW * factor), 2)


def generate_synthetic_solar_history(weather_history: pd.DataFrame) -> pd.DataFrame:
    rows = [{"timestamp": w["timestamp"], "solar_kw": _solar_output_kw(w)} for _, w in weather_history.iterrows()]
    return pd.DataFrame(rows)


def _train_rf(features: pd.DataFrame, target: np.ndarray) -> RandomForestRegressor:
    model = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=config.RANDOM_SEED)
    model.fit(features, target)
    return model


def _time_features(timestamps: pd.Series) -> pd.DataFrame:
    hour = timestamps.dt.hour + timestamps.dt.minute / 60.0
    return pd.DataFrame(
        {
            "hour_sin": np.sin(2 * np.pi * hour / 24.0),
            "hour_cos": np.cos(2 * np.pi * hour / 24.0),
            "is_weekend": (timestamps.dt.weekday >= 5).astype(int),
        }
    )


def forecast_demand(
    demand_history: pd.DataFrame,
    weather_history: pd.DataFrame,
    weather_forecast: pd.DataFrame,
) -> pd.DataFrame:
    train_df = demand_history.merge(weather_history, on="timestamp")
    X = pd.concat([_time_features(train_df["timestamp"]), train_df[["temperature_c"]]], axis=1)
    model = _train_rf(X, train_df["demand_kw"].values)

    future_X = pd.concat(
        [_time_features(weather_forecast["timestamp"]), weather_forecast[["temperature_c"]]], axis=1
    )
    preds = np.clip(model.predict(future_X), 30, None)
    return pd.DataFrame({"timestamp": weather_forecast["timestamp"], "demand_kw": np.round(preds, 2)})


def forecast_solar(
    solar_history: pd.DataFrame,
    weather_history: pd.DataFrame,
    weather_forecast: pd.DataFrame,
) -> pd.DataFrame:
    # Solar is driven almost entirely by weather: a learned correction
    # model trained on the synthetic history is applied to the forecast
    # weather rather than re-deriving an independent solar assumption.
    train_df = solar_history.merge(weather_history, on="timestamp")
    X = train_df[["cloud_cover_pct", "solar_irradiance_wm2"]]
    model = _train_rf(X, train_df["solar_kw"].values)

    future_X = weather_forecast[["cloud_cover_pct", "solar_irradiance_wm2"]]
    preds = np.clip(model.predict(future_X), 0, config.SOLAR_CAPACITY_KW)
    return pd.DataFrame({"timestamp": weather_forecast["timestamp"], "solar_kw": np.round(preds, 2)})


def compute_net_load(demand: pd.DataFrame, solar: pd.DataFrame) -> pd.DataFrame:
    merged = demand.merge(solar, on="timestamp")
    merged["net_load_kw"] = (merged["demand_kw"] - merged["solar_kw"]).round(2)
    merged["surplus_kw"] = merged["net_load_kw"].apply(lambda v: round(-v, 2) if v < 0 else 0.0)
    merged["curtailment_risk_kw"] = merged["surplus_kw"].apply(
        lambda s: round(max(0.0, s - config.FEEDER_EXPORT_LIMIT_KW), 2)
    )

    # Grid import/export implied by this net load with NO battery in the
    # loop (the battery module models its own, generally better, dispatch
    # separately -- see battery_service._baseline for the same shape of
    # calculation applied there). Export is whatever surplus the feeder
    # can actually absorb; curtailment_risk_kw above is the part it can't.
    merged["grid_import_kw"] = merged["net_load_kw"].clip(lower=0).round(2)
    merged["grid_export_kw"] = (merged["surplus_kw"] - merged["curtailment_risk_kw"]).round(2)

    # Renewable utilization: of the solar actually generated this hour,
    # how much was used locally or exported rather than curtailed.
    merged["utilized_solar_kw"] = (merged["solar_kw"] - merged["curtailment_risk_kw"]).round(2)
    merged["renewable_utilization_pct"] = merged.apply(
        lambda r: round(100.0 * r["utilized_solar_kw"] / r["solar_kw"], 1) if r["solar_kw"] > 0.01 else 100.0,
        axis=1,
    )
    return merged


def grid_stress_score(net_load_df: pd.DataFrame) -> pd.DataFrame:
    """
    0-100 composite score per hour, combining how close net load is to
    peak demand capacity, the ramp rate between consecutive hours, and
    curtailment pressure from unexportable surplus.
    """
    df = net_load_df.copy()
    df["ramp_kw"] = df["net_load_kw"].diff().abs().fillna(0.0)

    load_component = (df["net_load_kw"].clip(lower=0) / config.PEAK_DEMAND_KW).clip(0, 1)
    ramp_component = (df["ramp_kw"] / (config.PEAK_DEMAND_KW * 0.25)).clip(0, 1)
    curtailment_component = (df["curtailment_risk_kw"] / (config.FEEDER_EXPORT_LIMIT_KW * 0.5)).clip(0, 1)

    score = 100 * (0.5 * load_component + 0.25 * ramp_component + 0.25 * curtailment_component)
    df["grid_stress_score"] = score.round(1)
    df["stress_level"] = pd.cut(
        df["grid_stress_score"],
        bins=[-0.1, 30, 60, 100.1],
        labels=["low", "elevated", "high"],
    ).astype(str)
    return df


def build_energy_snapshot(weather_history: pd.DataFrame, weather_forecast: pd.DataFrame) -> dict:
    demand_history = generate_synthetic_demand_history(weather_history)
    solar_history = generate_synthetic_solar_history(weather_history)

    demand_forecast = forecast_demand(demand_history, weather_history, weather_forecast)
    solar_forecast = forecast_solar(solar_history, weather_history, weather_forecast)

    history_net = grid_stress_score(compute_net_load(demand_history, solar_history))
    forecast_net = grid_stress_score(compute_net_load(demand_forecast, solar_forecast))

    return {
        "history": history_net,
        "forecast": forecast_net,
        "demand_history": demand_history,
        "solar_history": solar_history,
    }
