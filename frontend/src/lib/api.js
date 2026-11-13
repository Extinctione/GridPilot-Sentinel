// Central place for the backend base URL and shared fetch helpers.
// Every module (weather, energy, battery, cyber, correlation,
// recommendations) has its functions here so pages stay thin.

export const API_BASE = "http://localhost:8000";

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (networkErr) {
    // fetch() throws (rather than resolving with a response) on a network
    // failure, a blocked CORS request, or the backend not listening at
    // all. These all look identical to the browser, so say so explicitly
    // instead of letting a vague "Failed to fetch" reach the user.
    throw new Error(
      `Could not reach the backend at ${API_BASE}${path}. Make sure it is running and that this page's origin is allowed by its CORS settings. (${networkErr.message})`
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ? `: ${JSON.stringify(body.detail)}` : "";
    } catch {
      // response had no JSON body -- ignore
    }
    throw new Error(`Request to ${path} failed with status ${res.status}${detail}`);
  }
  return res.json();
}

export const getHealth = () => request("/api/health");

export const getCurrentWeather = () => request("/api/weather/current");
export const getWeatherForecast = (hours = 24) => request(`/api/weather/forecast?hours=${hours}`);
export const getWeatherHistory = (hours = 72) => request(`/api/weather/history?hours=${hours}`);

export const getEnergyStatus = () => request("/api/energy/status");
export const getEnergyForecast = (hours = 24) => request(`/api/energy/forecast?hours=${hours}`);
export const getEnergyHistory = (hours = 72) => request(`/api/energy/history?hours=${hours}`);

export const getBatteryStatus = () => request("/api/battery/status");
export const getBatterySchedule = () => request("/api/battery/schedule");
export const optimizeBattery = (params) =>
  request("/api/battery/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

export const getCyberSummary = () => request("/api/cyber/summary");
export const getCyberEvents = (limit = 50, onlyAnomalies = false) =>
  request(`/api/cyber/events?limit=${limit}&only_anomalies=${onlyAnomalies}`);
export const getAssetGraph = () => request("/api/cyber/graph");

export const getCrossDomainRisks = () => request("/api/correlation/risks");
export const getRecommendations = () => request("/api/recommendations");

export const refreshSimulation = () => request("/api/weather/refresh");
