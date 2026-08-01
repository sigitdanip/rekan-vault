import re
from typing import Any, MutableMapping

import structlog

REDACT_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "cookie",
    "secret",
    "password",
    "api_key",
    "private_key",
    "token",
}

SECRET_PATTERN = re.compile(
    r"(ya29\.[0-9A-Za-z_-]+|secret_[0-9A-Za-z_-]+|Bearer\s+[0-9A-Za-z_.-]+)",
    re.IGNORECASE,
)


def redact_sensitive_data(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    def _redact_value(val: Any) -> Any:
        if isinstance(val, str):
            return SECRET_PATTERN.sub("[REDACTED]", val)
        elif isinstance(val, dict):
            return {k: ("[REDACTED]" if k.lower() in REDACT_KEYS else _redact_value(v)) for k, v in val.items()}
        elif isinstance(val, list):
            return [_redact_value(item) for item in val]
        return val

    result: MutableMapping[str, Any] = _redact_value(dict(event_dict))
    return result


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_sensitive_data,
    ]
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
