"""Logging configuration with optional JSON structured output."""

import json
import logging
import sys
from datetime import datetime, timezone

from terminal.enums import LogLevels
from terminal.config import settings


class JSONFormatter(logging.Formatter):
    """Emits log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id from contextvars if available
        try:
            from terminal.middleware import request_id_var

            rid = request_id_var.get("")
            if rid:
                log_entry["request_id"] = rid
        except ImportError:
            pass

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields
        for key in ("duration_ms", "status_code", "method", "path"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, default=str)


LOG_FORMAT_DEBUG = "%(levelname)s:%(message)s:%(pathname)s:%(funcName)s:%(lineno)d"
LOG_FORMAT_DEFAULT = "%(levelname)s:%(name)s:%(message)s"


def configure_logging():
    log_level = str(settings.log_level).upper()
    log_levels = list(LogLevels)

    if log_level not in log_levels:
        log_level = LogLevels.error

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Use JSON format in production, human-readable in development
    log_format = getattr(settings, "log_format", "text")
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    elif log_level == LogLevels.debug:
        handler.setFormatter(logging.Formatter(LOG_FORMAT_DEBUG))
    else:
        handler.setFormatter(logging.Formatter(LOG_FORMAT_DEFAULT))

    root.addHandler(handler)
