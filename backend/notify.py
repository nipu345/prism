"""Best-effort client for the Node/Nodemailer notification microservice.

Notifications are a nice-to-have, not a critical path: a slow or down
notification service must never fail (or even slow down) the analysis
response, so every failure mode here is swallowed and logged.
"""

import logging
import httpx
import config

logger = logging.getLogger("prism.notify")


def notify_report_ready(email: str, filename: str, report_id: str) -> None:
    if not email:
        return
    try:
        headers = {"x-api-key": config.NOTIFY_SERVICE_API_KEY} if config.NOTIFY_SERVICE_API_KEY else {}
        httpx.post(
            config.NOTIFY_SERVICE_URL,
            json={
                "to": email,
                "filename": filename,
                "reportUrl": f"{config.FRONTEND_URL}/results/{report_id}",
            },
            headers=headers,
            timeout=3.0,
        )
    except Exception as e:
        logger.warning("notification service unreachable: %s", e)
