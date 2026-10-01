"""Optional webhook for fills, stops, and the daily summary.

``WEBHOOK_URL`` or the config value is a Slack-compatible incoming webhook
(JSON POST with a ``text`` field) or any endpoint that accepts
``{"event": ..., "text": ...}``. Failures are logged by the caller; they
never block a fill.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import request


def webhook_url(config_value: str = "") -> str:
    return os.environ.get("WEBHOOK_URL") or config_value or ""


def notify(url: str, event: str, text: str, extra: dict[str, Any] | None = None) -> bool:
    if not url:
        return False
    body = {"event": event, "text": text}
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300
    except Exception:
        return False
