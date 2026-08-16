import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import client from "../api/client"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, LineChart, Line
} from "recharts"

const SCENARIOS = [
  { key: "conservative", label: "Conservative", subtitle: "Pessimistic case", color: "text-blue-400", bg: "bg-blue-500/10 border-blue-500/20", line: "#3B82F6" },
  { key: "moderate", label: "Moderate", subtitle: "Expected case", color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20", line: "#8B5CF6" },
  { key: "aggressive", label: "Aggressive", subtitle: "Optimistic case", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/20", line: "#F97316" },
]

function StatTile({ label, value }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-gray-400 text-sm">{label}</p>
      <p className="text-2xl font-semibold text-white mt-1">{value}</p>
    </div>
  )
}

function ModelCaption({ agent }) {
  const mape = agent.backtest?.mape
  return (
    <p className="text-xs text-gray-500 mt-2">
      Model: <span className="text-gray-400">{agent.model_used}</span>
      {mape !== undefined && mape !== null && (
        <> · Backtested accuracy: <span className="text-gray-400">{(100 - mape).toFixed(1)}%</span> (MAPE {mape}%, {agent.backtest?.holdout_days}-day holdout)</>
      )}
    </p>
  )
}

function ForecastChart({ agent, color }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h4 className="text-sm font-medium text-gray-400 mb-4">{agent.forecast_days}-day revenue forecast</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={agent.forecast}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="day" tick={{ fill: "#9CA3AF", fontSize: 12 }} />
          <YAxis tick={{ fill: "#9CA3AF", fontSize: 12 }} />
          <Tooltip contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: "8px" }} />
          <Line type="monotone" dataKey="predicted_revenue" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function Results() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeScenario, setActiveScenario] = useState("conservative")

  useEffect(() => {
    let ignore = false

    client.get(`/analysis/reports/${reportId}`)
      .then(res => { if (!ignore) setReport(res.data) })
      .catch(err => console.error(err))
      .finally(() => { if (!ignore) setLoading(false) })

    return () => { ignore = true }
  }, [reportId])

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-400">Loading results...</p>
    </div>
  )

  if (!report) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-400">Report not found</p>
    </div>
  )

  const active = SCENARIOS.find(s => s.key === activeScenario)
  const agent = report[activeScenario]

  const regionData = report.conservative?.revenue_by_region
    ? Object.entries(report.conservative.revenue_by_region).map(([region, revenue]) => ({ region, revenue }))
    : []

  const productData = report.conservative?.revenue_by_product
    ? Object.entries(report.conservative.revenue_by_product).map(([product, revenue]) => ({ product, revenue }))
    : []

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold cursor-pointer" onClick={() => navigate("/dashboard")}>Prism</h1>
        <button onClick={() => navigate("/dashboard")} className="text-gray-400 hover:text-white text-sm transition-colors">
          ← Back to dashboard
        </button>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-semibold mb-2">Analysis results</h2>
        <p className="text-gray-400 mb-6">Three risk scenarios, each backed by a backtested forecasting model</p>

        {report.ai_summary && (
          <div className="bg-gradient-to-br from-violet-500/10 to-blue-500/10 border border-violet-500/20 rounded-xl p-6 mb-8">
            <p className="text-xs font-semibold text-violet-400 uppercase tracking-wide mb-2">AI executive summary</p>
            <p className="text-gray-200 leading-relaxed">{report.ai_summary}</p>
          </div>
        )}

        {/* Scenario selector */}
        <div className="flex gap-3 mb-8">
          {SCENARIOS.map(s => (
            <button
              key={s.key}
              onClick={() => setActiveScenario(s.key)}
              className={`px-5 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                activeScenario === s.key
                  ? s.bg + " " + s.color
                  : "border-gray-700 text-gray-400 hover:border-gray-600"
              }`}
            >
              {s.label}
              <span className="block text-[10px] font-normal opacity-70">{s.subtitle}</span>
            </button>
          ))}
        </div>

        {!agent ? (
          <div className="text-gray-400">No data for this scenario.</div>
        ) : agent.error ? (
          <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-xl p-5">
            {agent.error}
          </div>
        ) : (
          <div className="space-y-6">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h3 className={`text-lg font-semibold mb-1 ${active.color}`}>{agent.scenario || active.subtitle}</h3>
              <p className="text-gray-300">{agent.insight}</p>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <StatTile label={`${agent.forecast_days}-day forecast`} value={`$${agent.forecasted_total_revenue?.toLocaleString()}`} />
              <StatTile label="Daily average" value={`$${agent.forecasted_daily_average?.toLocaleString()}`} />
              <StatTile
                label="Backtested accuracy"
                value={agent.backtest?.mape != null ? `${(100 - agent.backtest.mape).toFixed(1)}%` : "N/A"}
              />
            </div>

            <div>
              <ForecastChart agent={agent} color={active.line} />
              <ModelCaption agent={agent} />
            </div>

            {activeScenario === "conservative" && (
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                  <h4 className="text-sm font-medium text-gray-400 mb-4">Revenue by region</h4>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={regionData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="region" tick={{ fill: "#9CA3AF", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#9CA3AF", fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: "8px" }} />
                      <Bar dataKey="revenue" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                  <h4 className="text-sm font-medium text-gray-400 mb-4">Revenue by product</h4>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={productData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="product" tick={{ fill: "#9CA3AF", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#9CA3AF", fontSize: 12 }} />
                      <Tooltip contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: "8px" }} />
                      <Bar dataKey="revenue" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {activeScenario === "aggressive" && (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <StatTile label="Anomalies found" value={agent.anomalies_found} />
                  <StatTile label="Best product" value={agent.best_performing_product ?? "—"} />
                  <StatTile label="Underperforming regions" value={agent.underperforming_regions?.length ?? 0} />
                </div>

                {agent.anomalies?.length > 0 && (
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h4 className="text-sm font-medium text-gray-400 mb-4">Detected anomalies (risk factors)</h4>
                    <div className="space-y-3">
                      {agent.anomalies.map((a, i) => (
                        <div key={i} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                          <div>
                            <p className="text-white text-sm font-medium">{a.date}</p>
                            <p className="text-gray-400 text-xs">{a.product} · {a.region}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-white text-sm">${a.revenue?.toLocaleString()}</p>
                            <p className="text-gray-400 text-xs">{a.units_sold} units</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {agent.underperforming_regions?.length > 0 && (
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h4 className="text-sm font-medium text-gray-400 mb-3">Underperforming regions</h4>
                    <div className="flex gap-2 flex-wrap">
                      {agent.underperforming_regions.map(r => (
                        <span key={r} className="bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm px-3 py-1 rounded-full">
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
