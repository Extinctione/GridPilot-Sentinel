"""
Central configuration and simulation constants for GridPilot Sentinel.

Nothing here talks to a real electricity grid. All values are defaults
for a synthetic simulation / decision-support exercise and can be
overridden per-request where the API exposes that (e.g. battery sizing).
"""

from __future__ import annotations

# --- Simulation window -------------------------------------------------
HISTORY_HOURS = 24 * 7        # one week of synthetic history
FORECAST_HOURS = 24           # 24-hour-ahead forecasts
RANDOM_SEED = 42

# --- Site characteristics ------------------------------------------------
SITE_LATITUDE = 12.9716        # Bengaluru, used only as a plausible default
SITE_LONGITUDE = 77.5946
SOLAR_CAPACITY_KW = 500.0      # installed PV capacity for the simulated feeder
FEEDER_EXPORT_LIMIT_KW = 350.0  # grid's ability to absorb exported surplus
PEAK_DEMAND_KW = 600.0

# --- Battery defaults (overridable per optimization request) ------------
BATTERY_CAPACITY_KWH = 400.0
BATTERY_MAX_CHARGE_KW = 120.0
BATTERY_MAX_DISCHARGE_KW = 120.0
BATTERY_CHARGE_EFFICIENCY = 0.95
BATTERY_DISCHARGE_EFFICIENCY = 0.95
BATTERY_MIN_SOC_FRACTION = 0.1
BATTERY_MAX_SOC_FRACTION = 0.95
BATTERY_INITIAL_SOC_FRACTION = 0.5

# --- Illustrative tariff used only to compare dispatch strategies -------
GRID_IMPORT_PRICE_PER_KWH = 8.0
GRID_EXPORT_PRICE_PER_KWH = 3.0
CURTAILMENT_PENALTY_PER_KWH = 1.5

# --- Cyber / asset graph --------------------------------------------------
GRID_ASSETS = [
    {"id": "SCADA-CTRL-1", "type": "scada_controller", "criticality": "high"},
    {"id": "SUBSTN-A", "type": "substation", "criticality": "high"},
    {"id": "SUBSTN-B", "type": "substation", "criticality": "high"},
    {"id": "INVERTER-PV-1", "type": "solar_inverter", "criticality": "medium"},
    {"id": "INVERTER-PV-2", "type": "solar_inverter", "criticality": "medium"},
    {"id": "BESS-CTRL-1", "type": "battery_controller", "criticality": "high"},
    {"id": "SMART-METER-CLUSTER-1", "type": "meter_cluster", "criticality": "low"},
    {"id": "SMART-METER-CLUSTER-2", "type": "meter_cluster", "criticality": "low"},
    {"id": "RTU-FEEDER-1", "type": "remote_terminal_unit", "criticality": "medium"},
    {"id": "HMI-OPS-1", "type": "operator_hmi", "criticality": "medium"},
]

GRID_ASSET_LINKS = [
    ("HMI-OPS-1", "SCADA-CTRL-1"),
    ("SCADA-CTRL-1", "SUBSTN-A"),
    ("SCADA-CTRL-1", "SUBSTN-B"),
    ("SCADA-CTRL-1", "BESS-CTRL-1"),
    ("SCADA-CTRL-1", "RTU-FEEDER-1"),
    ("SUBSTN-A", "INVERTER-PV-1"),
    ("SUBSTN-A", "SMART-METER-CLUSTER-1"),
    ("SUBSTN-B", "INVERTER-PV-2"),
    ("SUBSTN-B", "SMART-METER-CLUSTER-2"),
    ("RTU-FEEDER-1", "SUBSTN-A"),
    ("RTU-FEEDER-1", "SUBSTN-B"),
    ("BESS-CTRL-1", "SUBSTN-A"),
]

MODEL_CACHE_DIR = "ml_models"
PIPELINE_REFRESH_SECONDS = 600  # regenerate the shared simulation every 10 min
