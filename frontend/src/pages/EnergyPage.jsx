import { ResponsiveContainer, ComposedChart, Line, Area, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { useApiData } from "../lib/useApiData.js";
import { getEnergyStatus, getEnergyForecast, getEnergyHistory } from "../lib/api.js";
import LoadingState from "../components/LoadingState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import StatCard from "../components/StatCard.jsx";

function formatHour(ts) {
  return new Date(ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" });
}

export default function EnergyPage() {
  const status = useApiData(getEnergyStatus);
  const forecast = useApiData(() => getEnergyForecast(24));
  const history = useApiData(() => getEnergyHistory(48));

  const loading = status.loading || forecast.loading || history.loading;
  const error = status.error || forecast.error || history.error;

  if (loading) return <LoadingState label="Loading energy intelligence..." />;
  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          status.reload();
          forecast.reload();
          history.reload();
        }}
      />
    );

  const chartData = [...history.data.history, ...forecast.data.forecast].map((row) => ({
    ...row,
    label: formatHour(row.timestamp),
  }));

  const stressTone =
    status.data.current.grid_stress_score >= 60 ? "bad" : status.data.current.grid_stress_score >= 30 ? "warn" : "good";

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Energy Intelligence</h2>
        <p className="text-sm text-textmuted">
          Demand and solar forecasts, net load, renewable surplus and grid-stress scoring.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Current Demand" value={`${status.data.current.demand_kw} kW`} />
        <StatCard label="Current Solar" value={`${status.data.current.solar_kw} kW`} />
        <StatCard
          label="Grid Stress"
          value={status.data.current.grid_stress_score}
          tone={stressTone}
          sublabel={status.data.current.stress_level}
        />
        <StatCard
          label="Forecast Curtailment Risk"
          value={`${status.data.total_forecast_curtailment_risk_kwh.toFixed(0)} kWh`}
          tone={status.data.total_forecast_curtailment_risk_kwh > 0 ? "warn" : "good"}
        />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-80">
        <div className="text-sm font-medium mb-2">Demand vs Solar vs Net Load (history → forecast)</div>
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

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-72">
        <div className="text-sm font-medium mb-2">Grid Stress Score (0-100)</div>
        <ResponsiveContainer width="100%" height="90%">
          <ComposedChart data={chartData}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis domain={[0, 100]} tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Bar dataKey="grid_stress_score" name="Grid Stress" fill="#EF4444" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
