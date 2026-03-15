"""
Centralised logging configuration for SmartOps.
Supports both file and console logging with rotation.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def setup_logging(
    name: str = "smartops",
    level: str = "INFO",
    log_file: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure and return a named logger.

    Args:
        name:         Logger name (module name).
        level:        Log level string: DEBUG, INFO, WARNING, ERROR.
        log_file:     Path to log file. If None, logs to console only.
        max_bytes:    Max log file size before rotation.
        backup_count: Number of rotated log files to keep.

    Returns:
        Configured logging.Logger instance.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers on re-initialisation
    if logger.handlers:
        return logger

    # ── Console handler ───────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # ── File handler (rotating) ───────────────
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the smartops namespace.

    Usage:
        from shared.logging_config import get_logger
        logger = get_logger(__name__)
    """
    # Ensure root smartops logger is set up with env config
    level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/smartops.log")

    # Set up root once
    root = logging.getLogger("smartops")
    if not root.handlers:
        setup_logging(
            name="smartops",
            level=level,
            log_file=log_file,
        )

    return logging.getLogger(f"smartops.{name}")
