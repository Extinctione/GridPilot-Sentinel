import { useState } from "react";
import { useApiData } from "../lib/useApiData.js";
import { getCyberSummary, getCyberEvents } from "../lib/api.js";
import LoadingState from "../components/LoadingState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import StatCard from "../components/StatCard.jsx";

export default function CyberPage() {
  const [onlyAnomalies, setOnlyAnomalies] = useState(true);
  const summary = useApiData(getCyberSummary);
  const events = useApiData(() => getCyberEvents(100, onlyAnomalies), [onlyAnomalies]);

  if (summary.loading || events.loading) return <LoadingState label="Scoring cyber telemetry..." />;
  if (summary.error || events.error)
    return (
      <ErrorState
        message={summary.error || events.error}
        onRetry={() => {
          summary.reload();
          events.reload();
        }}
      />
    );

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Cyber Intelligence</h2>
        <p className="text-sm text-textmuted">
          Isolation-Forest anomaly detection over synthetic grid-cybersecurity telemetry.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Events" value={summary.data.total_events} />
        <StatCard label="Anomalies" value={summary.data.anomaly_count} tone={summary.data.anomaly_count > 0 ? "warn" : "good"} />
        <StatCard label="Anomaly Rate" value={`${summary.data.anomaly_rate_pct}%`} />
        <StatCard label="Highest-Risk Asset" value={summary.data.highest_risk_asset || "—"} />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium">Events</div>
          <label className="flex items-center gap-2 text-xs text-textmuted">
            <input type="checkbox" checked={onlyAnomalies} onChange={(e) => setOnlyAnomalies(e.target.checked)} />
            Anomalies only
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-textmuted border-b border-panelborder">
                <th className="py-2 pr-4">Event</th>
                <th className="py-2 pr-4">Asset</th>
                <th className="py-2 pr-4">Risk Score</th>
                <th className="py-2 pr-4">Why it was flagged</th>
              </tr>
            </thead>
            <tbody>
              {events.data.events.map((e) => (
                <tr key={e.event_id} className="border-b border-panelborder/50">
                  <td className="py-2 pr-4 font-mono">{e.event_id}</td>
                  <td className="py-2 pr-4">{e.asset_id}</td>
                  <td
                    className={`py-2 pr-4 ${
                      e.risk_score >= 60 ? "text-accentred" : e.risk_score >= 30 ? "text-accentamber" : "text-accentgreen"
                    }`}
                  >
                    {e.risk_score}
                  </td>
                  <td className="py-2 pr-4 text-textmuted">{e.contributing_factors.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.data.events.length === 0 && <p className="text-textmuted text-sm py-4">No events match this filter.</p>}
        </div>
      </div>
    </div>
  );
}
