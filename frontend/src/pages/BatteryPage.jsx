import { useState } from "react";
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { useApiData } from "../lib/useApiData.js";
import { getBatterySchedule, getBatteryStatus, optimizeBattery } from "../lib/api.js";
import LoadingState from "../components/LoadingState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import StatCard from "../components/StatCard.jsx";

function formatHour(ts) {
  return new Date(ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" });
}

const DEFAULT_PARAMS = {
  capacity_kwh: 400,
  max_charge_kw: 120,
  max_discharge_kw: 120,
  charge_efficiency: 0.95,
  discharge_efficiency: 0.95,
  min_soc_fraction: 0.1,
  max_soc_fraction: 0.95,
  initial_soc_fraction: 0.5,
};

export default function BatteryPage() {
  const schedule = useApiData(getBatterySchedule);
  const status = useApiData(getBatteryStatus);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [customResult, setCustomResult] = useState(null);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeError, setOptimizeError] = useState(null);

  if (schedule.loading || status.loading) return <LoadingState label="Running battery optimization..." />;
  if (schedule.error || status.error)
    return (
      <ErrorState
        message={schedule.error || status.error}
        onRetry={() => {
          schedule.reload();
          status.reload();
        }}
      />
    );

  const rows = customResult
    ? customResult.schedule.map((r) => ({ ...r, label: formatHour(r.timestamp) }))
    : schedule.data.schedule.map((r) => ({ ...r, label: formatHour(r.timestamp) }));

  const totalCost = customResult ? customResult.total_cost : schedule.data.total_cost;
  const baselineCost = customResult ? customResult.baseline_cost : schedule.data.baseline_cost;
  const savings = customResult ? customResult.cost_savings : schedule.data.cost_savings;

  // Capacity / SOC / solver status come from whichever result is active:
  // the live pipeline's battery status, or the last custom re-optimize.
  const capacityKwh = customResult ? customResult.capacity_kwh : status.data.parameters.capacity_kwh;
  const initialSocPct = customResult ? customResult.initial_soc_pct : status.data.initial_soc_pct;
  const finalSocPct = customResult ? customResult.final_soc_pct : status.data.final_soc_pct;
  const solverStatus = customResult ? customResult.status : status.data.status;
  const solverOk = solverStatus === "Optimal";

  async function handleOptimize(e) {
    e.preventDefault();
    setOptimizing(true);
    setOptimizeError(null);
    try {
      const result = await optimizeBattery(params);
      const timestamps = schedule.data.schedule.map((r) => r.timestamp);
      setCustomResult({
        schedule: result.soc_pct.map((_, i) => ({
          timestamp: timestamps[i],
          charge_kw: result.charge_kw[i],
          discharge_kw: result.discharge_kw[i],
          soc_pct: result.soc_pct[i],
          grid_import_kw: result.grid_import_kw[i],
          grid_export_kw: result.grid_export_kw[i],
          curtailed_kw: result.curtailed_kw[i],
          baseline_grid_import_kw: result.baseline.grid_import_kw[i],
          baseline_grid_export_kw: result.baseline.grid_export_kw[i],
          baseline_curtailed_kw: result.baseline.curtailed_kw[i],
        })),
        total_cost: result.total_cost,
        baseline_cost: result.baseline.total_cost,
        cost_savings: result.cost_savings,
        capacity_kwh: result.parameters.capacity_kwh,
        initial_soc_pct: result.initial_soc_pct,
        final_soc_pct: result.final_soc_pct,
        status: result.status,
      });
    } catch (err) {
      // The backend now returns 422 with a clear message (invalid params,
      // or the solver genuinely couldn't find a feasible/optimal plan) --
      // show that message rather than a fabricated schedule.
      setOptimizeError(err.message);
    } finally {
      setOptimizing(false);
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Battery Optimization</h2>
        <p className="text-sm text-textmuted">
          PuLP-based linear program dispatching the battery across the 24-hour forecast horizon.
        </p>
      </div>

      {!solverOk && (
        <div className="rounded-lg border border-accentred/40 bg-accentred/10 p-3 text-sm text-accentred">
          Solver status: <span className="font-mono">{solverStatus}</span> -- this schedule is not a confirmed
          optimal solution and should not be relied on.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Battery Capacity" value={`${capacityKwh} kWh`} />
        <StatCard label="Initial SOC" value={`${initialSocPct}%`} />
        <StatCard label="Final SOC" value={`${finalSocPct}%`} sublabel="End of 24h horizon" />
        <StatCard label="Solver Status" value={solverStatus} tone={solverOk ? "good" : "bad"} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard label="Optimized Cost" value={totalCost} />
        <StatCard label="Baseline Cost (no battery)" value={baselineCost} />
        <StatCard label="Savings" value={savings} tone={savings > 0 ? "good" : "default"} />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-80">
        <div className="text-sm font-medium mb-2">Charge / Discharge / State of Charge</div>
        <ResponsiveContainer width="100%" height="90%">
          <ComposedChart data={rows}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis yAxisId="left" tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Legend />
            <Bar yAxisId="left" dataKey="charge_kw" name="Charge (kW)" fill="#3B82F6" />
            <Bar yAxisId="left" dataKey="discharge_kw" name="Discharge (kW)" fill="#F59E0B" />
            <Line yAxisId="right" type="monotone" dataKey="soc_pct" name="SOC (%)" stroke="#22C55E" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-80">
        <div className="text-sm font-medium mb-2">Grid Import/Export: Before vs After Optimization</div>
        <ResponsiveContainer width="100%" height="90%">
          <ComposedChart data={rows}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Legend />
            <Line type="monotone" dataKey="baseline_grid_import_kw" name="Baseline Import (kW)" stroke="#8B98A9" strokeDasharray="4 3" dot={false} />
            <Line type="monotone" dataKey="grid_import_kw" name="Optimized Import (kW)" stroke="#3B82F6" dot={false} />
            <Line type="monotone" dataKey="baseline_grid_export_kw" name="Baseline Export (kW)" stroke="#8B98A9" dot={false} />
            <Line type="monotone" dataKey="grid_export_kw" name="Optimized Export (kW)" stroke="#22C55E" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <form onSubmit={handleOptimize} className="rounded-lg border border-panelborder bg-panel p-4 space-y-3">
        <div className="text-sm font-medium">Re-run optimizer with different battery parameters</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["capacity_kwh", "Capacity (kWh)"],
            ["max_charge_kw", "Max Charge (kW)"],
            ["max_discharge_kw", "Max Discharge (kW)"],
            ["initial_soc_fraction", "Initial SOC (0-1)"],
          ].map(([key, label]) => (
            <label key={key} className="text-xs text-textmuted flex flex-col gap-1">
              {label}
              <input
                type="number"
                step="any"
                value={params[key]}
                onChange={(e) => setParams((p) => ({ ...p, [key]: parseFloat(e.target.value) }))}
                className="rounded-md bg-bg border border-panelborder px-2 py-1 text-textprimary"
              />
            </label>
          ))}
        </div>
        <button
          type="submit"
          disabled={optimizing}
          className="rounded-md bg-accentgreen/20 border border-accentgreen/40 text-accentgreen px-3 py-1.5 text-sm hover:bg-accentgreen/30 disabled:opacity-50"
        >
          {optimizing ? "Optimizing..." : "Re-optimize"}
        </button>
        {optimizeError && <ErrorState message={optimizeError} />}
      </form>
    </div>
  );
}
