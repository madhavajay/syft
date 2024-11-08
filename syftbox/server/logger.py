import logging
import sys
from pathlib import Path
from typing import Union

from loguru import logger

custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level}</level> | <cyan>{message}</cyan>"

USER_EVENT = "user_event"


def default_log_filter(record: dict):
    return record["extra"].get("event_type") != USER_EVENT


def user_event_filter(record: dict):
    return record["extra"].get("event_type") == USER_EVENT


user_event_logger = logger.bind(event_type=USER_EVENT)


def setup_logger(logs_dir: Path, level: Union[str, int] = "DEBUG"):
    logger.remove()

    # Standard server logs
    logger.add(
        level=level,
        sink=sys.stderr,
        diagnose=False,
        backtrace=False,
        format=custom_format,
        filter=default_log_filter,
    )

    logger.add(
        logs_dir / "server.log",
        rotation="100 MB",  # Rotate after the log file reaches 100 MB
        retention=2,  # Keep only the last 1 log files
        compression="zip",  # Usually, 10x reduction in file size
        filter=default_log_filter,
    )

    # Dedicated logger for user events
    # example usage: user_event_logger.info("User logged in")
    logger.add(
        logs_dir / "user_events.json",
        rotation="100 MB",
        retention=2,
        compression="zip",
        serialize=True,
        filter=user_event_filter,
    )

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True
