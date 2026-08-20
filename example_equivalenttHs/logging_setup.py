"""Shared loguru logging setup for the EWH project task scripts.

Ensures every script logs to both the console and a per-script, timestamped log file under
`logs/`, using a single-line format (no multi-line tracebacks/messages breaking the log layout).
"""

import sys
from datetime import datetime, timezone

from loguru import logger

from constants import LOG_DIR

_SINGLE_LINE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | "
    "{message}"
)


def setup_logging(script_name: str) -> str:
    """Configure loguru for a task script and return the log file path.

    Args:
        script_name: Short name of the calling script, e.g. "00_fetch_spectra".

    Returns:
        The path to the created log file, as a string.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%dT%H_%M_%S")
    log_path = LOG_DIR / f"{script_name}_{timestamp}.log"

    logger.remove()
    logger.add(sys.stderr, format=_SINGLE_LINE_FORMAT, level="INFO", enqueue=True)
    logger.add(
        log_path,
        format=_SINGLE_LINE_FORMAT,
        level="DEBUG",
        enqueue=True,
        diagnose=False,
        backtrace=False,
    )
    logger.info("Logging initialized for '{}', writing to {}", script_name, log_path)
    return str(log_path)
