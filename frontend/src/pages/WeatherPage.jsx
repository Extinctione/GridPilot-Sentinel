import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { useApiData } from "../lib/useApiData.js";
import { getCurrentWeather, getWeatherForecast, getWeatherHistory } from "../lib/api.js";
import LoadingState from "../components/LoadingState.jsx";
import ErrorState from "../components/ErrorState.jsx";
import StatCard from "../components/StatCard.jsx";

function formatHour(ts) {
  return new Date(ts).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" });
}

export default function WeatherPage() {
  const current = useApiData(getCurrentWeather);
  const forecast = useApiData(() => getWeatherForecast(24));
  const history = useApiData(() => getWeatherHistory(72));

  const loading = current.loading || forecast.loading || history.loading;
  const error = current.error || forecast.error || history.error;

  if (loading) return <LoadingState label="Loading weather intelligence..." />;
  if (error)
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          current.reload();
          forecast.reload();
          history.reload();
        }}
      />
    );

  const chartData = [...history.data.history, ...forecast.data.forecast].map((row) => ({
    ...row,
    label: formatHour(row.timestamp),
  }));

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Weather Intelligence</h2>
        <p className="text-sm text-textmuted">
          Synthetic weather history plus a 24-hour ML forecast that feeds the energy module.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Temperature" value={`${current.data.temperature_c}°C`} />
        <StatCard label="Humidity" value={`${current.data.humidity_pct}%`} />
        <StatCard label="Cloud Cover" value={`${current.data.cloud_cover_pct}%`} />
        <StatCard label="Wind Speed" value={`${current.data.wind_speed_kmh} km/h`} />
        <StatCard label="Irradiance" value={`${current.data.solar_irradiance_wm2} W/m²`} />
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-80">
        <div className="text-sm font-medium mb-2">Temperature & Solar Irradiance (history → forecast)</div>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={chartData}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis yAxisId="left" tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="temperature_c" name="Temp (°C)" stroke="#F59E0B" dot={false} />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="solar_irradiance_wm2"
              name="Irradiance (W/m²)"
              stroke="#22C55E"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-panelborder bg-panel p-4 h-72">
        <div className="text-sm font-medium mb-2">Cloud Cover & Wind Speed</div>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={chartData}>
            <CartesianGrid stroke="#1E2A3A" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fill: "#8B98A9", fontSize: 10 }} minTickGap={30} />
            <YAxis tick={{ fill: "#8B98A9", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#121823", border: "1px solid #1E2A3A" }} />
            <Legend />
            <Line type="monotone" dataKey="cloud_cover_pct" name="Cloud Cover (%)" stroke="#8B98A9" dot={false} />
            <Line type="monotone" dataKey="wind_speed_kmh" name="Wind (km/h)" stroke="#3B82F6" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
