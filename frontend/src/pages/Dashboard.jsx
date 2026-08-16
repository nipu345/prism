import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../context/useAuth"
import client from "../api/client"

export default function Dashboard() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [uploads, setUploads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let ignore = false

    client.get("/uploads/list")
      .then(res => { if (!ignore) setUploads(res.data) })
      .catch(err => console.error(err))
      .finally(() => { if (!ignore) setLoading(false) })

    return () => { ignore = true }
  }, [])

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Prism</h1>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/upload")}
            className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            New analysis
          </button>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="max-w-5xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-semibold mb-2">Your analyses</h2>
        <p className="text-gray-400 mb-8">Upload company sales data to generate risk-scenario revenue forecasts</p>

        {loading ? (
          <div className="text-gray-400">Loading...</div>
        ) : uploads.length === 0 ? (
          <div className="border border-dashed border-gray-700 rounded-2xl p-16 text-center">
            <p className="text-gray-400 text-lg mb-4">No analyses yet</p>
            <button
              onClick={() => navigate("/upload")}
              className="bg-violet-600 hover:bg-violet-500 text-white font-medium px-6 py-2.5 rounded-lg transition-colors"
            >
              Upload your first file
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {uploads.map(upload => (
              <div
                key={upload.id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between hover:border-gray-700 transition-colors"
              >
                <div>
                  <p className="font-medium text-white">{upload.filename}</p>
                  <p className="text-sm text-gray-400 mt-1">{upload.row_count} rows · {new Date(upload.uploaded_at).toLocaleDateString()}</p>
                </div>
                <button
                  onClick={() => navigate(`/results/${upload.id}`)}
                  className="text-violet-400 hover:text-violet-300 text-sm font-medium transition-colors"
                >
                  View results →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}