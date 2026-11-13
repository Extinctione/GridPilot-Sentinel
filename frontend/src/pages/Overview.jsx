import { ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { useApiData } from "../lib/useApiData.js";
import {
  getEnergyStatus,
  getEnergyForecast,
  getEnergyHistory,
  getBatteryStatus,
  getCyberSummary,
  getRecommendations,
} from "../lib/api.js";
import LoadingState from "../components/LoadingState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import StatCard from "../components/StatCard.jsx";

function formatHour(ts) {
  return new Date(ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" });
}

export default function Overview() {
  const energy = useApiData(getEnergyStatus);
  const forecast = useApiData(() => getEnergyForecast(24));
  const history = useApiData(() => getEnergyHistory(24));
  const battery = useApiData(getBatteryStatus);
  const cyber = useApiData(getCyberSummary);
  const recs = useApiData(getRecommendations);

  const loading = energy.loading || forecast.loading || history.loading || battery.loading || cyber.loading || recs.loading;
  const error = energy.error || forecast.error || history.error || battery.error || cyber.error || recs.error;

  const reloadAll = () => {
    energy.reload();
    forecast.reload();
    history.reload();
    battery.reload();
    cyber.reload();
    recs.reload();
  };

  if (loading) return <LoadingState label="Loading grid overview..." />;
  if (error) return <ErrorState message={error} onRetry={reloadAll} />;

  const current = energy.data.current;
  const chartData = [...history.data.history, ...forecast.data.forecast].map((row) => ({
    ...row,
    label: formatHour(row.timestamp),
  }));

  if (chartData.length === 0) {
    return <ErrorState message="No energy history or forecast data is available yet." onRetry={reloadAll} />;
  }

  const stressTone = current.grid_stress_score >= 60 ? "bad" : current.grid_stress_score >= 30 ? "warn" : "good";
  const isSurplus = current.net_load_kw < 0;
  const utilTone = current.renewable_utilization_pct >= 90 ? "good" : current.renewable_utilization_pct >= 70 ? "warn" : "bad";
  const curtailTone = current.curtailment_risk_kw > 0 ? "warn" : "good";
  const highPriorityCount = recs.data.recommendations.filter((r) => r.priority === "high").length;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Grid Overview</h2>
        <p className="text-sm text-textmuted">
          Live snapshot of the simulated feeder, as of {new Date(current.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}.
          All figures come from the decision-support simulation -- GridPilot Sentinel does not control real grid infrastructure.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Demand" value={`${current.demand_kw} kW`} />
        <StatCard label="Renewable (Solar) Generation" value={`${current.solar_kw} kW`} />
        <StatCard label="Grid Import" value={`${current.grid_import_kw} kW`} sublabel="Drawn from the grid" />
        <StatCard label="Grid Export" value={`${current.grid_export_kw} kW`} sublabel="Surplus sent to the grid" />
        <StatCard
          label="Energy Balance"
          value={isSurplus ? `+${current.surplus_kw} kW` : `${current.net_load_kw} kW`}
          sublabel={isSurplus ? "Renewable surplus" : "Deficit (needs import)"}
          tone={isSurplus ? "good" : "default"}
        />
        <StatCard
          label="Grid Stress"
          value={current.grid_stress_score}
          sublabel={current.stress_level}
          tone={stressTone}
        />
        <StatCard
          label="Renewable Utilization"
          value={`${current.renewable_utilization_pct}%`}
          sublabel="Solar used vs. generated"
          tone={utilTone}
        />
        <StatCard
          label="Curtailment Risk"
          value={`${current.curtailment_risk_kw} kW`}
          sublabel={`${energy.data.total_forecast_curtailment_risk_kwh.toFixed(0)} kWh over next 24h`}
          tone={curtailTone}
        />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-80">
        <div className="text-sm font-medium mb-2">Demand vs Renewable Generation (last 24h history, next 24h forecast)</div>
        <ResponsiveContainer width="100%" height="90%">
          <ComposedChart data={chartData}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Legend />
            <Area type="monotone" dataKey="solar_kw" name="Solar (kW)" fill="#22C55E33" stroke="#22C55E" />
            <Line type="monotone" dataKey="demand_kw" name="Demand (kW)" stroke="#3B82F6" dot={false} />
            <Line type="monotone" dataKey="net_load_kw" name="Net Load (kW)" stroke="#F59E0B" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard
          label="Battery Savings"
          value={battery.data.cost_savings}
          sublabel="vs. no-battery baseline"
          tone={battery.data.cost_savings > 0 ? "good" : "default"}
        />
        <StatCard
          label="Cyber Anomalies"
          value={cyber.data.anomaly_count}
          sublabel={`of ${cyber.data.total_events} recent events`}
          tone={cyber.data.anomaly_count > 0 ? "warn" : "good"}
        />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4">
        <div className="text-sm font-medium mb-2">Recommendations needing attention</div>
        {highPriorityCount === 0 ? (
          <p className="text-sm text-textmuted">No high-priority recommendations right now.</p>
        ) : (
          <p className="text-sm text-textmuted">
            {highPriorityCount} high-priority recommendation(s) -- see the Recommendations tab.
          </p>
        )}
      </div>
    </div>
  );
}
