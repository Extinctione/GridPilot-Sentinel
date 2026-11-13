"""
Recommendations.

Turns the outputs of the other modules into a short, prioritized list
of concrete, explainable actions. Every recommendation carries the
metric that triggered it and a plain-language rationale.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd


def build_recommendations(
    energy_forecast: pd.DataFrame,
    battery_result: dict,
    cyber_summary: dict,
    cross_domain_risks: List[Dict],
) -> List[Dict]:
    recs: List[Dict] = []

    peak_row = energy_forecast.loc[energy_forecast["grid_stress_score"].idxmax()]
    if peak_row["grid_stress_score"] >= 60:
        recs.append(
            {
                "id": "rec-high-stress-hour",
                "priority": "high",
                "title": "Pre-position battery discharge ahead of peak stress",
                "explanation": (
                    f"The forecast shows its highest grid-stress reading around {peak_row['timestamp']}. "
                    "Discharging the battery into that window reduces how much the feeder has to "
                    "import at the moment it is most constrained."
                ),
                "metrics": {
                    "peak_grid_stress_score": float(peak_row["grid_stress_score"]),
                    "peak_hour": str(peak_row["timestamp"]),
                },
                "suggested_action": "Schedule battery discharge to ramp up 1-2 hours before the forecast peak-stress hour.",
            }
        )

    total_curtailment = float(energy_forecast["curtailment_risk_kw"].sum())
    if total_curtailment > 0:
        recs.append(
            {
                "id": "rec-curtailment-risk",
                "priority": "high" if total_curtailment > 200 else "medium",
                "title": "Increase surplus absorption to reduce curtailment",
                "explanation": (
                    "Forecast solar surplus exceeds the feeder's export limit in at least one hour. "
                    "Charging the battery -- or shifting flexible load -- during these hours converts "
                    "otherwise-wasted generation into stored or consumed energy."
                ),
                "metrics": {"total_forecast_curtailment_risk_kw": round(total_curtailment, 1)},
                "suggested_action": "Shift battery charging and any deferrable loads into the highest-surplus forecast hours.",
            }
        )

    if battery_result.get("cost_savings", 0) > 0:
        recs.append(
            {
                "id": "rec-battery-savings",
                "priority": "medium",
                "title": "Adopt the optimized battery dispatch plan",
                "explanation": (
                    "The optimizer's dispatch plan is projected to cost less than a no-battery "
                    "baseline over the same horizon while respecting capacity and state-of-charge limits."
                ),
                "metrics": {
                    "projected_cost_savings": battery_result.get("cost_savings"),
                    "curtailment_avoided_kwh": battery_result.get("curtailment_avoided_kwh"),
                },
                "suggested_action": "Use the optimizer's charge/discharge schedule as the dispatch target for the next horizon.",
            }
        )

    if cyber_summary.get("anomaly_count", 0) > 0:
        recs.append(
            {
                "id": "rec-cyber-review",
                "priority": "high" if cyber_summary.get("average_risk_score", 0) >= 50 else "medium",
                "title": "Review highest-risk cyber events",
                "explanation": (
                    f"{cyber_summary.get('anomaly_count')} event(s) out of {cyber_summary.get('total_events')} "
                    f"were flagged as anomalous, most concentrated on {cyber_summary.get('highest_risk_asset')}."
                ),
                "metrics": {
                    "anomaly_count": cyber_summary.get("anomaly_count"),
                    "anomaly_rate_pct": cyber_summary.get("anomaly_rate_pct"),
                    "highest_risk_asset": cyber_summary.get("highest_risk_asset"),
                },
                "suggested_action": "Have an operator review the top-ranked anomalous events and confirm whether access was authorized.",
            }
        )

    for risk in cross_domain_risks:
        if risk["id"] == "no-cross-domain-risk":
            continue
        recs.append(
            {
                "id": f"rec-{risk['id']}",
                "priority": risk["severity"],
                "title": f"Address overlapping risk: {risk['title']}",
                "explanation": risk["explanation"],
                "metrics": {"domains": risk["domains"]},
                "suggested_action": "Treat this as a combined operational-and-security review item, not a routine single-domain alert.",
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 3))
    return recs
