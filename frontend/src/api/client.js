import axios from "axios"

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
})

// Attach the bearer token to every request automatically instead of each
// page reading localStorage and setting the header by hand.
client.interceptors.request.use((requestConfig) => {
  const token = localStorage.getItem("token")
  if (token) {
    requestConfig.headers.authorization = `Bearer ${token}`
  }
  return requestConfig
})

export default client
