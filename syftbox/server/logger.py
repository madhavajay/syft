import logging
import sys
from pathlib import Path
from shutil import make_archive
from typing import Union

from loguru import logger

from syftbox.lib.lib import DEFAULT_LOGS_PATH

custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level}</level> | <cyan>{message}</cyan>"


def setup_logger(level: Union[str, int] = "DEBUG", log_file: Union[Path, str] = DEFAULT_LOGS_PATH):
    # TODO set configurable log path per client (once new folder structure is merged)
    logger.remove()
    logger.add(level=level, sink=sys.stderr, diagnose=False, backtrace=False, format=custom_format)

    # Configure Loguru to write logs to a file with rotation
    logger.add(
        log_file,
        rotation="100 MB",  # Rotate after the log file reaches 100 MB
        retention=2,  # Keep only the last 1 log files
        compression="zip",  # Usually, 10x reduction in file size
    )

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True


def zip_logs(output_path):
    logs_folder = Path(DEFAULT_LOGS_PATH).parent
    return make_archive(output_path, "zip", logs_folder)
