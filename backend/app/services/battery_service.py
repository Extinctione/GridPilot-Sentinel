"""
Battery Optimization.

Formulates an hourly battery dispatch problem as a Mixed-Integer Linear
Program (PuLP, CBC solver) that minimizes net grid cost -- import cost
minus export revenue, plus a curtailment penalty -- over the forecast
horizon, subject to capacity, power and state-of-charge constraints,
with a binary variable that forbids simultaneous charging and
discharging.

A no-battery "baseline" scenario is computed for the same horizon so
callers can report optimized-vs-baseline savings.
"""

from __future__ import annotations

from typing import List

import pulp

from app.core import config


def _baseline(net_load_kw: List[float]) -> dict:
    """What the feeder would do with no battery at all."""
    grid_import, grid_export, curtailed = [], [], []
    for v in net_load_kw:
        imp = max(0.0, v)
        surplus = max(0.0, -v)
        exp = min(surplus, config.FEEDER_EXPORT_LIMIT_KW)
        curt = surplus - exp
        grid_import.append(round(imp, 2))
        grid_export.append(round(exp, 2))
        curtailed.append(round(curt, 2))

    cost = (
        sum(g * config.GRID_IMPORT_PRICE_PER_KWH for g in grid_import)
        - sum(e * config.GRID_EXPORT_PRICE_PER_KWH for e in grid_export)
        + sum(c * config.CURTAILMENT_PENALTY_PER_KWH for c in curtailed)
    )
    return {
        "grid_import_kw": grid_import,
        "grid_export_kw": grid_export,
        "curtailed_kw": curtailed,
        "total_cost": round(cost, 2),
        "total_curtailed_kwh": round(sum(curtailed), 2),
    }


def optimize(
    net_load_kw: List[float],
    capacity_kwh: float = config.BATTERY_CAPACITY_KWH,
    max_charge_kw: float = config.BATTERY_MAX_CHARGE_KW,
    max_discharge_kw: float = config.BATTERY_MAX_DISCHARGE_KW,
    charge_eff: float = config.BATTERY_CHARGE_EFFICIENCY,
    discharge_eff: float = config.BATTERY_DISCHARGE_EFFICIENCY,
    min_soc_frac: float = config.BATTERY_MIN_SOC_FRACTION,
    max_soc_frac: float = config.BATTERY_MAX_SOC_FRACTION,
    initial_soc_frac: float = config.BATTERY_INITIAL_SOC_FRACTION,
) -> dict:
    """
    Solve one hour-resolution dispatch problem over len(net_load_kw) hours.
    net_load_kw[t] > 0 means the feeder needs power (demand > solar);
    net_load_kw[t] < 0 means there is renewable surplus available.

    Raises ValueError for invalid/out-of-range inputs, and RuntimeError if
    the solver does not return an optimal solution -- callers must never
    treat a non-"Optimal" status as a usable schedule.
    """
    if not net_load_kw:
        raise ValueError("net_load_kw must contain at least one hour of forecast data.")
    if capacity_kwh <= 0:
        raise ValueError(f"capacity_kwh must be positive, got {capacity_kwh}.")
    if max_charge_kw <= 0 or max_discharge_kw <= 0:
        raise ValueError(
            f"max_charge_kw and max_discharge_kw must be positive, got {max_charge_kw} and {max_discharge_kw}."
        )
    if not (0 < charge_eff <= 1) or not (0 < discharge_eff <= 1):
        raise ValueError(
            f"charge_efficiency and discharge_efficiency must be in (0, 1], got {charge_eff} and {discharge_eff}."
        )
    if not (0 <= min_soc_frac < max_soc_frac <= 1):
        raise ValueError(
            f"Require 0 <= min_soc_fraction < max_soc_fraction <= 1, got {min_soc_frac} and {max_soc_frac}."
        )
    if not (min_soc_frac <= initial_soc_frac <= max_soc_frac):
        raise ValueError(
            f"initial_soc_fraction ({initial_soc_frac}) must lie within "
            f"[min_soc_fraction, max_soc_fraction] = [{min_soc_frac}, {max_soc_frac}]."
        )

    T = range(len(net_load_kw))
    min_soc = capacity_kwh * min_soc_frac
    max_soc = capacity_kwh * max_soc_frac
    initial_soc = capacity_kwh * initial_soc_frac

    prob = pulp.LpProblem("battery_dispatch", pulp.LpMinimize)

    charge = pulp.LpVariable.dicts("charge_kw", T, lowBound=0, upBound=max_charge_kw)
    discharge = pulp.LpVariable.dicts("discharge_kw", T, lowBound=0, upBound=max_discharge_kw)
    is_charging = pulp.LpVariable.dicts("is_charging", T, cat="Binary")
    soc = pulp.LpVariable.dicts("soc_kwh", T, lowBound=min_soc, upBound=max_soc)
    grid_import = pulp.LpVariable.dicts("grid_import_kw", T, lowBound=0)
    grid_export = pulp.LpVariable.dicts("grid_export_kw", T, lowBound=0, upBound=config.FEEDER_EXPORT_LIMIT_KW)
    curtailed = pulp.LpVariable.dicts("curtailed_kw", T, lowBound=0)
    terminal_deficit = pulp.LpVariable("terminal_soc_deficit", lowBound=0)

    for t in T:
        # No simultaneous charge/discharge: both are gated by one shared binary.
        prob += charge[t] <= max_charge_kw * is_charging[t]
        prob += discharge[t] <= max_discharge_kw * (1 - is_charging[t])

        # State of charge evolves with round-trip-efficiency-adjusted flows.
        prev_soc = initial_soc if t == 0 else soc[t - 1]
        prob += soc[t] == prev_soc + charge[t] * charge_eff - discharge[t] * (1.0 / discharge_eff)

        # Power balance at the point of common coupling: sinks (net load,
        # charging, export, curtailment) must equal sources (import,
        # discharging). net_load_kw[t] is negative when solar > demand,
        # which is what lets surplus flow into export/curtailment here.
        prob += net_load_kw[t] + charge[t] - discharge[t] + grid_export[t] + curtailed[t] == grid_import[t]

    # Soft preference (not a hard constraint, to avoid infeasibility) for
    # ending the horizon close to where the battery started.
    prob += terminal_deficit >= initial_soc - soc[len(net_load_kw) - 1]

    prob += pulp.lpSum(
        grid_import[t] * config.GRID_IMPORT_PRICE_PER_KWH
        - grid_export[t] * config.GRID_EXPORT_PRICE_PER_KWH
        + curtailed[t] * config.CURTAILMENT_PENALTY_PER_KWH
        for t in T
    ) + 0.01 * terminal_deficit

    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        # Do NOT fall through to result extraction: LpVariable.value() is
        # None on an infeasible/unbounded/not-solved problem, and silently
        # coercing that to 0.0 below would report a fabricated all-zero
        # schedule as if it were a real optimized dispatch plan.
        raise RuntimeError(
            f"Battery optimizer did not find an optimal solution (solver status: {status}). "
            "Check that min_soc_fraction < max_soc_fraction, that initial_soc_fraction falls "
            "inside that range, and that capacity/power limits are physically sensible."
        )
    baseline = _baseline(net_load_kw)

    result = {
        "status": status,
        "charge_kw": [round(charge[t].value() or 0.0, 2) for t in T],
        "discharge_kw": [round(discharge[t].value() or 0.0, 2) for t in T],
        "soc_kwh": [round(soc[t].value() or 0.0, 2) for t in T],
        "soc_pct": [round(100 * (soc[t].value() or 0.0) / capacity_kwh, 1) for t in T],
        "grid_import_kw": [round(grid_import[t].value() or 0.0, 2) for t in T],
        "grid_export_kw": [round(grid_export[t].value() or 0.0, 2) for t in T],
        "curtailed_kw": [round(curtailed[t].value() or 0.0, 2) for t in T],
        "baseline": baseline,
        "parameters": {
            "capacity_kwh": capacity_kwh,
            "max_charge_kw": max_charge_kw,
            "max_discharge_kw": max_discharge_kw,
            "charge_efficiency": charge_eff,
            "discharge_efficiency": discharge_eff,
        },
    }
    result["initial_soc_kwh"] = round(initial_soc, 2)
    result["initial_soc_pct"] = round(100 * initial_soc / capacity_kwh, 1)
    result["final_soc_pct"] = result["soc_pct"][-1]
    grid_cost = sum(
        (result["grid_import_kw"][t] * config.GRID_IMPORT_PRICE_PER_KWH)
        - (result["grid_export_kw"][t] * config.GRID_EXPORT_PRICE_PER_KWH)
        + (result["curtailed_kw"][t] * config.CURTAILMENT_PENALTY_PER_KWH)
        for t in T
    )
    result["total_cost"] = round(grid_cost, 2)
    result["total_curtailed_kwh"] = round(sum(result["curtailed_kw"]), 2)
    result["cost_savings"] = round(baseline["total_cost"] - result["total_cost"], 2)
    result["curtailment_avoided_kwh"] = round(baseline["total_curtailed_kwh"] - result["total_curtailed_kwh"], 2)
    return result
