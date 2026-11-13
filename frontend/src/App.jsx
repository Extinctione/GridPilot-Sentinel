import { useEffect, useState } from 'react'
import { getHealth } from './lib/api.js'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import Overview from './pages/Overview.jsx'
import WeatherPage from './pages/WeatherPage.jsx'
import EnergyPage from './pages/EnergyPage.jsx'
import BatteryPage from './pages/BatteryPage.jsx'
import CyberPage from './pages/CyberPage.jsx'

// Asset Network, Cross-Domain Analysis and Recommendations pages are not
// built yet -- deliberately left as an honest placeholder below rather
// than imported, so this file never claims a module exists before it does.
const MODULES = [
  { id: 'overview', label: 'Grid Overview', component: Overview },
  { id: 'weather', label: 'Weather Intelligence', component: WeatherPage },
  { id: 'energy', label: 'Energy Intelligence', component: EnergyPage },
  { id: 'battery', label: 'Battery Optimization', component: BatteryPage },
  { id: 'cyber', label: 'Cyber Intelligence', component: CyberPage },
  { id: 'network', label: 'Asset Network', component: null },
  { id: 'crossdomain', label: 'Cross-Domain Analysis', component: null },
  { id: 'recommendations', label: 'Recommendations', component: null },
]

function StatusPill({ status }) {
  const color =
    status === 'connected'
      ? 'bg-accentgreen'
      : status === 'checking'
      ? 'bg-accentamber'
      : 'bg-accentred'
  const text =
    status === 'connected'
      ? 'Backend connected'
      : status === 'checking'
      ? 'Checking backend...'
      : 'Backend unreachable'
  return (
    <div className="flex items-center gap-2 text-sm text-textmuted">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      {text}
    </div>
  )
}

export default function App() {
  const [activeModule, setActiveModule] = useState('overview')
  const [backendStatus, setBackendStatus] = useState('checking')

  useEffect(() => {
    getHealth()
      .then(() => setBackendStatus('connected'))
      .catch(() => setBackendStatus('error'))
  }, [])

  const active = MODULES.find((m) => m.id === activeModule) || MODULES[0]
  const ActiveComponent = active.component

  return (
    <div className="min-h-screen bg-bg text-textprimary flex flex-col">
      <header className="border-b border-panelborder px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">GridPilot Sentinel</h1>
          <p className="text-xs text-textmuted">
            Challenge 14 — The Grid That Cannot Absorb the Sun · Decision-support simulation, not a live grid controller
          </p>
        </div>
        <StatusPill status={backendStatus} />
      </header>

      <div className="flex flex-1">
        <nav className="w-60 border-r border-panelborder p-4 space-y-1">
          {MODULES.map((m) => (
            <button
              key={m.id}
              onClick={() => setActiveModule(m.id)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                activeModule === m.id
                  ? 'bg-panel text-textprimary border border-panelborder'
                  : 'text-textmuted hover:text-textprimary hover:bg-panel/60'
              }`}
            >
              {m.label}
              {!m.component && <span className="ml-2 text-[10px] text-textmuted/60">(soon)</span>}
            </button>
          ))}
        </nav>

        <main className="flex-1 p-6 overflow-y-auto">
          {backendStatus === 'error' && (
            <div className="rounded-lg border border-accentred/40 bg-accentred/10 p-4 text-sm text-accentred max-w-2xl mb-6">
              Could not reach the backend at http://localhost:8000. Start it with{' '}
              <code className="mx-1 px-1 py-0.5 rounded bg-bg">uvicorn app.main:app --reload</code>
              from the <code className="mx-1 px-1 py-0.5 rounded bg-bg">backend</code> folder (inside{' '}
              <code className="mx-1 px-1 py-0.5 rounded bg-bg">venv</code>), then reload this page.
            </div>
          )}

          {ActiveComponent ? (
            // key={active.id} remounts (and so resets) the boundary and the
            // page's own hooks when switching modules, instead of carrying
            // a previous crash or stale request state into the new page.
            <ErrorBoundary key={active.id}>
              <ActiveComponent />
            </ErrorBoundary>
          ) : (
            <div className="max-w-2xl">
              <h2 className="text-xl font-semibold mb-2">{active.label}</h2>
              <p className="text-sm text-textmuted">
                This module has not been built yet. It is next in line after Overview, Weather,
                Energy, Battery and Cyber Intelligence.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
