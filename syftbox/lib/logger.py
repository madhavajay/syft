import sys
from pathlib import Path
from shutil import make_archive
from typing import Union

from loguru import logger

from syftbox.lib.lib import DEFAULT_LOGS_PATH


def setup_logger(level: Union[str, int] = "DEBUG", log_file: Union[Path, str] = DEFAULT_LOGS_PATH):
    # TODO set configurable log path per client (once new folder structure is merged)
    logger.remove()
    logger.add(level=level, sink=sys.stderr, diagnose=False, backtrace=False)

    # Configure Loguru to write logs to a file with rotation
    logger.add(
        log_file,
        rotation="100 MB",  # Rotate after the log file reaches 100 MB
        retention=2,  # Keep only the last 1 log files
        compression="zip",  # Usually, 10x reduction in file size
    )


def zip_logs(output_path):
    logs_folder = Path(DEFAULT_LOGS_PATH).parent
    return make_archive(output_path, "zip", logs_folder)


setup_logger()
