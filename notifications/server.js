import express from "express"
import cors from "cors"
import dotenv from "dotenv"
import nodemailer from "nodemailer"

dotenv.config()

const PORT = process.env.PORT || 4000
const API_KEY = process.env.NOTIFY_API_KEY || ""

const app = express()
app.use(cors())
app.use(express.json())

// Lazily built + cached so we only create one transporter (and, in dev,
// only one Ethereal test account) for the life of the process.
let transporterPromise = null

async function getTransporter() {
  if (transporterPromise) return transporterPromise

  transporterPromise = (async () => {
    if (process.env.SMTP_HOST) {
      return nodemailer.createTransport({
        host: process.env.SMTP_HOST,
        port: Number(process.env.SMTP_PORT || 587),
        secure: process.env.SMTP_SECURE === "true",
        auth: process.env.SMTP_USER
          ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
          : undefined,
      })
    }

    // No SMTP configured — fall back to a disposable Ethereal test inbox so
    // this service is fully runnable/demoable without real credentials.
    // Swap in real SMTP_* env vars (Gmail app password, SendGrid, etc.) to
    // send real email.
    const testAccount = await nodemailer.createTestAccount()
    console.log(`[notifications] No SMTP_HOST set — using an Ethereal test inbox (${testAccount.user})`)
    return nodemailer.createTransport({
      host: "smtp.ethereal.email",
      port: 587,
      secure: false,
      auth: { user: testAccount.user, pass: testAccount.pass },
    })
  })()

  return transporterPromise
}

app.get("/health", (req, res) => res.json({ status: "ok" }))

app.post("/notify-report", async (req, res) => {
  if (API_KEY && req.headers["x-api-key"] !== API_KEY) {
    return res.status(401).json({ error: "Invalid API key" })
  }

  const { to, filename, reportUrl } = req.body || {}
  if (!to) return res.status(400).json({ error: "'to' is required" })

  try {
    const transporter = await getTransporter()
    const info = await transporter.sendMail({
      from: process.env.FROM_EMAIL || '"Prism" <notifications@prism.app>',
      to,
      subject: `Your forecast for ${filename || "your upload"} is ready`,
      text: `Your revenue forecast${filename ? ` for ${filename}` : ""} is ready.${reportUrl ? ` View it here: ${reportUrl}` : ""}`,
      html:
        `<p>Your revenue forecast${filename ? ` for <strong>${filename}</strong>` : ""} is ready.</p>` +
        (reportUrl ? `<p><a href="${reportUrl}">View your results</a></p>` : ""),
    })

    const previewUrl = nodemailer.getTestMessageUrl(info)
    if (previewUrl) console.log(`[notifications] Preview: ${previewUrl}`)

    res.json({ status: "sent", previewUrl: previewUrl || null })
  } catch (err) {
    console.error("[notifications] send failed:", err.message)
    res.status(502).json({ error: "Failed to send notification" })
  }
})

app.listen(PORT, () => console.log(`[notifications] listening on :${PORT}`))
