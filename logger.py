"""
logger.py — centralised logging configuration for the entire project.

Creates a single 'movie_search' logger that writes to:
  - errors_log.log — ERROR level and above (errors only).
  - Console        — WARNING level and above (warnings + errors).

Usage in any project module:
    from logger import get_logger
    log = get_logger(__name__)
    log.error("Connection failed: %s", exc)
"""

import logging
from pathlib import Path

# Log file is created next to this module, regardless of working directory
_LOG_FILE: Path = Path(__file__).parent / 'errors_log.log'

_FORMATTER = logging.Formatter(
    fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


def _build_logger() -> logging.Logger:
    """
    Creates and configures the project root logger.
    Called once on module import.
    """
    logger = logging.getLogger('movie_search')

    # Do not add handlers if the logger is already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File handler: ERROR and above only
    file_handler = logging.FileHandler(_LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(_FORMATTER)

    # Console handler: WARNING and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(_FORMATTER)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


_logger = _build_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Returns a child logger named after the calling module.

    Child loggers automatically propagate records to the parent
    ('movie_search'), so all messages end up in one file.

    Args:
        name: Typically passed as __name__ from the calling module.

    Returns:
        A ready-to-use logging.Logger instance.

    Example:
        log = get_logger(__name__)
        log.error("Write failed: %s", exc)
    """
    return logging.getLogger(f'movie_search.{name}')
