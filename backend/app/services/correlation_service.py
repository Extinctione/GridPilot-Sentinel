"""
Cross-Domain Intelligence.

Looks for operationally meaningful overlaps between energy/grid stress,
battery state, and cyber anomalies. Every finding is reported as a
timing *association* together with the evidence that produced it --
this module deliberately never claims that one domain caused another.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

_CONTROL_ASSETS = {"SCADA-CTRL-1", "BESS-CTRL-1", "RTU-FEEDER-1"}


def find_cross_domain_risks(
    energy_forecast: pd.DataFrame,
    battery_result: dict,
    cyber_summary: dict,
    cyber_events: pd.DataFrame,
) -> List[Dict]:
    findings: List[Dict] = []

    # 1. Grid stress coinciding with anomalies on control-plane assets.
    high_stress_hours = energy_forecast[energy_forecast["grid_stress_score"] >= 60]
    control_anomalies = cyber_events[cyber_events["is_anomaly"] & cyber_events["asset_id"].isin(_CONTROL_ASSETS)]
    if not high_stress_hours.empty and not control_anomalies.empty:
        findings.append(
            {
                "id": "stress-x-control-anomaly",
                "title": "Elevated grid stress overlaps with control-system anomalies",
                "severity": "high",
                "domains": ["energy", "cyber"],
                "evidence": [
                    f"{len(high_stress_hours)} forecast hour(s) with a grid-stress score of 60 or higher.",
                    f"{len(control_anomalies)} anomalous event(s) on control-plane assets "
                    f"({', '.join(sorted(control_anomalies['asset_id'].unique()))}).",
                ],
                "explanation": (
                    "Operating a stressed feeder while its control systems show anomalous "
                    "activity compounds risk: a decision made under grid stress could be acted "
                    "on by a compromised or malfunctioning controller. This is a timing "
                    "association, not evidence that one caused the other."
                ),
            }
        )

    # 2. Renewable curtailment risk alongside anomalies on inverter assets.
    curtailment_hours = energy_forecast[energy_forecast["curtailment_risk_kw"] > 0]
    inverter_anomalies = cyber_events[
        cyber_events["is_anomaly"] & cyber_events["asset_id"].str.contains("INVERTER")
    ]
    if not curtailment_hours.empty and not inverter_anomalies.empty:
        findings.append(
            {
                "id": "curtailment-x-inverter-anomaly",
                "title": "Curtailment-risk hours coincide with inverter anomalies",
                "severity": "medium",
                "domains": ["energy", "cyber"],
                "evidence": [
                    f"{len(curtailment_hours)} forecast hour(s) with unexportable solar surplus.",
                    f"{len(inverter_anomalies)} anomalous event(s) on solar-inverter assets.",
                ],
                "explanation": (
                    "Surplus solar that already exceeds export capacity leaves little margin "
                    "for error; anomalous inverter telemetry during the same window makes "
                    "automated curtailment decisions harder to trust. The two signals are "
                    "reported together because they overlap in time, not because either has "
                    "been shown to cause the other."
                ),
            }
        )

    # 3. Battery near its SOC limits while overall cyber risk is elevated.
    low_soc = any(p < 15 for p in battery_result.get("soc_pct", []))
    high_cyber_risk = cyber_summary.get("average_risk_score", 0) >= 40
    if low_soc and high_cyber_risk:
        findings.append(
            {
                "id": "battery-limit-x-cyber-risk",
                "title": "Battery approaching state-of-charge limits during a noisy security period",
                "severity": "medium",
                "domains": ["battery", "cyber"],
                "evidence": [
                    "The optimized dispatch plan brings the battery below 15% state of charge "
                    "at least once in the forecast horizon.",
                    f"Average cyber risk score across recent events is {cyber_summary.get('average_risk_score')}.",
                ],
                "explanation": (
                    "A battery with little remaining headroom has less ability to absorb an "
                    "unexpected operational surprise. Manually reviewing battery commands is "
                    "reasonable while background cyber risk is elevated, though the two trends "
                    "are only associated by timing."
                ),
            }
        )

    if not findings:
        findings.append(
            {
                "id": "no-cross-domain-risk",
                "title": "No significant cross-domain overlap detected",
                "severity": "low",
                "domains": [],
                "evidence": ["Energy, battery and cyber signals did not meet the overlap thresholds this cycle."],
                "explanation": (
                    "This does not guarantee the absence of risk -- only that the specific "
                    "overlap patterns this module checks for were not observed."
                ),
            }
        )

    return findings
