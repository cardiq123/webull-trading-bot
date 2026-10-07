"""Logging that refuses to print credentials."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_SECRET_ENV = ("WEBULL_APP_KEY", "WEBULL_APP_SECRET", "WEBHOOK_URL")

# Header and body fields the official SDK prints at DEBUG, including x-app-key.
_SENSITIVE_FIELD = re.compile(
    r"(?i)((?:x-app-key|x-app-secret|app_key|app_secret|appkey|appsecret|"
    r"access_token|refresh_token|x-access-token|token)"
    r"['\"]?\s*[:=]\s*['\"]?)"
    r"([^'\"\s,}\]]+)"
)


def redact_text(message: str, secrets: list[str] | None = None) -> str:
    """Hide app keys, secrets, and session tokens in a log or report line."""
    for secret in secrets or []:
        if secret and len(secret) > 4 and secret in message:
            message = message.replace(secret, "[redacted]")
    return _SENSITIVE_FIELD.sub(r"\1[redacted]", message)


class SdkSecretFilter(logging.Filter):
    """Redact credentials on any logger, including the official SDK logger."""

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        env_secrets = [os.environ.get(name, "") for name in _SECRET_ENV]
        self._secrets = [s for s in list(secrets or []) + env_secrets if s and len(s) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self._secrets)
        record.args = ()
        return True


class _SecretFilter(SdkSecretFilter):
    def __init__(self) -> None:
        super().__init__()


def setup_logging(level: str = "INFO", log_dir: str | None = "logs") -> logging.Logger:
    logger = logging.getLogger("webull_bot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    stream.addFilter(_SecretFilter())
    logger.addHandler(stream)
    if log_dir:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path / "webull_bot.log")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_SecretFilter())
        logger.addHandler(file_handler)
    logger.propagate = False
    return logger
