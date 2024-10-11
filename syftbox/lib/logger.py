from loguru import logger

from syftbox.lib.lib import DEFAULT_LOGS_PATH

# Configure Loguru to write logs to a file with rotation
logger.add(
    DEFAULT_LOGS_PATH,
    rotation="20 KB",  # Rotate after the log file reaches 100 MB
    retention=1,  # Keep only the last 1 log files
    compression="zip",  # Usually, 10x reduction in file size
)
