from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from syftbox.server.logger import analytics_logger


def to_jsonable_dict(obj: dict) -> dict:
    """
    Convert log record to a JSON serializable dictionary.
    """
    result = {}
    for key, value in obj.items():
        if isinstance(value, dict):
            result[key] = to_jsonable_dict(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Path):
            result[key] = value.as_posix()
        elif isinstance(value, (str, int, float, bool, type(None))):
            result[key] = value
        else:
            result[key] = str(value)

    return result


def log_analytics_event(
    endpoint: str,
    email: str,
    message: str = "",
    **kwargs: Any,
):
    """
    Log an event to the analytics logger.
    """
    try:
        extra = {
            "email": email,
            "endpoint": endpoint,
            "timestamp": datetime.now(timezone.utc),
            **kwargs,
        }
        analytics_logger.bind(**extra).info(message)
    except Exception as e:
        logger.error(f"Failed to log event: {e}")
