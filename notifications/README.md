# Prism notifications service

Small Express + Nodemailer microservice. The FastAPI backend calls
`POST /notify-report` after an analysis completes; this service sends the
"your forecast is ready" email.

Kept as a separate service (rather than in the FastAPI backend) so it can be
deployed, scaled, and iterated on independently — a real notification
provider swap (e.g. moving off SMTP to Postmark/SendGrid) never touches the
Python codebase.

## Run it

```bash
cp .env.example .env
npm install
npm start
```

With no `SMTP_HOST` set, it automatically creates a disposable [Ethereal](https://ethereal.email)
test inbox on first send and logs a preview URL for every email — fully
demoable with zero real credentials. Set `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS`
(e.g. a Gmail app password, or SendGrid/Postmark SMTP credentials) to send
real email.

`NOTIFY_API_KEY` is a shared secret the backend sends as `x-api-key` — set
the same value in `backend/.env` (`NOTIFY_SERVICE_API_KEY`) so the two agree.
