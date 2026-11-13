"""
Cyber Intelligence.

Generates synthetic grid-cybersecurity telemetry, scores it with an
Isolation Forest, explains *why* an event looks anomalous via simple
per-feature deviation scoring, and builds a NetworkX graph of grid
assets so anomalies can be related to the infrastructure they touch.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.core import config

EVENT_FEATURES = [
    "packet_rate_pps",
    "auth_failures",
    "protocol_anomaly_score",
    "access_time_deviation_min",
    "data_volume_mb",
]

_FACTOR_LABELS = {
    "packet_rate_pps": "unusual packet rate",
    "auth_failures": "elevated authentication failures",
    "protocol_anomaly_score": "abnormal protocol behaviour",
    "access_time_deviation_min": "access at an unusual time",
    "data_volume_mb": "unusually large data transfer",
}


def generate_synthetic_events(n_events: int = 400, end: Optional[datetime] = None) -> pd.DataFrame:
    rng = np.random.default_rng(config.RANDOM_SEED + 7)
    end = end or datetime.now(timezone.utc)
    asset_ids = [a["id"] for a in config.GRID_ASSETS]

    n_anomalous = max(3, int(n_events * 0.04))
    n_normal = n_events - n_anomalous

    normal = pd.DataFrame(
        {
            "packet_rate_pps": rng.normal(120, 20, n_normal).clip(0),
            "auth_failures": rng.poisson(0.3, n_normal),
            "protocol_anomaly_score": rng.beta(1.5, 10, n_normal),
            "access_time_deviation_min": rng.normal(0, 4, n_normal),
            "data_volume_mb": rng.gamma(2, 3, n_normal),
        }
    )
    normal["asset_id"] = rng.choice(asset_ids, n_normal)
    normal["label_hint"] = "normal"

    anomalous = pd.DataFrame(
        {
            "packet_rate_pps": rng.normal(420, 90, n_anomalous).clip(0),
            "auth_failures": rng.poisson(6, n_anomalous),
            "protocol_anomaly_score": rng.beta(6, 2, n_anomalous),
            "access_time_deviation_min": rng.normal(0, 1, n_anomalous) + rng.choice([-180, 180], n_anomalous),
            "data_volume_mb": rng.gamma(9, 15, n_anomalous),
        }
    )
    # Anomalous traffic skews toward the highest-value control-system assets.
    high_value = [a["id"] for a in config.GRID_ASSETS if a["criticality"] == "high"]
    anomalous["asset_id"] = rng.choice(high_value, n_anomalous)
    anomalous["label_hint"] = "synthetic_anomaly"

    events = pd.concat([normal, anomalous], ignore_index=True)
    minute_offsets = rng.integers(0, 60 * 24 * 3, len(events))  # spread across ~3 days
    events["timestamp"] = [end - timedelta(minutes=int(m)) for m in minute_offsets]
    events = events.sort_values("timestamp").reset_index(drop=True)
    events["event_id"] = [f"EVT-{i:05d}" for i in range(len(events))]
    return events


def detect_anomalies(events: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    df = events.copy()
    X = df[EVENT_FEATURES].values
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=config.RANDOM_SEED)
    model.fit(X)
    raw_scores = model.decision_function(X)  # higher = more normal
    df["is_anomaly"] = model.predict(X) == -1

    span = raw_scores.max() - raw_scores.min() + 1e-9
    df["risk_score"] = np.round((raw_scores.max() - raw_scores) / span * 100, 1)

    means = df[EVENT_FEATURES].mean()
    stds = df[EVENT_FEATURES].std().replace(0, 1e-9)

    def explain(row) -> List[str]:
        z = ((row[EVENT_FEATURES] - means) / stds).abs().sort_values(ascending=False)
        top = z.head(2)
        reasons = [_FACTOR_LABELS[f] for f in top.index if z[f] > 1.5]
        return reasons or ["no single feature stands out sharply"]

    df["contributing_factors"] = df.apply(explain, axis=1)
    return df.sort_values("risk_score", ascending=False).reset_index(drop=True)


def build_asset_graph(scored_events: Optional[pd.DataFrame] = None) -> nx.Graph:
    graph = nx.Graph()
    for asset in config.GRID_ASSETS:
        graph.add_node(asset["id"], type=asset["type"], criticality=asset["criticality"])
    graph.add_edges_from(config.GRID_ASSET_LINKS)

    if scored_events is not None and not scored_events.empty:
        anomaly_counts = scored_events[scored_events["is_anomaly"]]["asset_id"].value_counts()
        for node in graph.nodes:
            graph.nodes[node]["anomaly_count"] = int(anomaly_counts.get(node, 0))
    else:
        for node in graph.nodes:
            graph.nodes[node]["anomaly_count"] = 0

    for node, value in nx.betweenness_centrality(graph).items():
        graph.nodes[node]["betweenness_centrality"] = round(value, 4)
    return graph


def graph_to_json(graph: nx.Graph) -> dict:
    nodes = [{"id": n, **graph.nodes[n]} for n in graph.nodes]
    edges = [{"source": u, "target": v} for u, v in graph.edges]
    return {"nodes": nodes, "edges": edges}


def summarize(scored_events: pd.DataFrame) -> dict:
    anomalies = scored_events[scored_events["is_anomaly"]]
    return {
        "total_events": int(len(scored_events)),
        "anomaly_count": int(len(anomalies)),
        "anomaly_rate_pct": round(100 * len(anomalies) / max(1, len(scored_events)), 2),
        "highest_risk_asset": (anomalies["asset_id"].value_counts().idxmax() if not anomalies.empty else None),
        "average_risk_score": round(float(scored_events["risk_score"].mean()), 1),
    }
