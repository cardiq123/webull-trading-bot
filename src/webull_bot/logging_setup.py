"""Logging that refuses to print credentials."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

_SECRET_ENV = ("WEBULL_APP_KEY", "WEBULL_APP_SECRET", "WEBHOOK_URL")


class _SecretFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        secrets = [os.environ.get(name, "") for name in _SECRET_ENV]
        self._patterns = [re.escape(s) for s in secrets if s and len(s) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = re.sub(pattern, "[redacted]", message)
        record.msg = message
        record.args = ()
        return True


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
