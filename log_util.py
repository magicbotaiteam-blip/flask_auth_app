"""
Unified logging configuration for Magic Bot AI.
Centralizes log file setup, rotation, and format.

Files created:
  logs/flask_app.log     - main application log (rotating, 10MB x 10 backups)
  logs/audit.log         - audit-specific log (separate from DB audit trail)
  logs/access.log        - HTTP access log (optional)

Env var: LOG_DIR=path   (default: logs/ in app root)
"""

import os
import logging
import logging.handlers
from datetime import datetime

LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FORMATTER = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

_loggers = {}  # cache


def get_logger(name: str) -> logging.Logger:
    """Get or create a named logger."""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    return _loggers[name]


def setup_file_logger(
    name: str,
    filename: str,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 10,
) -> logging.Logger:
    """Create or configure a file-based rotating logger.

    Args:
        name: Logger name.
        filename: Relative to LOG_DIR.
        level: Logging level.
        max_bytes: Max size before rotation.
        backup_count: Number of rotated files to keep.

    Returns:
        Configured logger.
    """
    ensure_log_dir()
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-init
    logger.handlers.clear()

    filepath = os.path.join(LOG_DIR, filename)
    handler = logging.handlers.RotatingFileHandler(
        filepath, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setFormatter(FORMATTER)
    logger.addHandler(handler)

    # Also add console handler for dev visibility
    console = logging.StreamHandler()
    console.setFormatter(FORMATTER)
    logger.addHandler(console)

    logger.propagate = False
    return logger


def ensure_log_dir():
    """Create log directory if it doesn't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def configure_app_logging(app_log_level: int = logging.INFO):
    """One-call setup for all log files.

    Call this once at app startup.
    """
    ensure_log_dir()

    # --- 1. Main application log ---
    app_log = setup_file_logger("app", "flask_app.log", app_log_level)
    app_log.info("=" * 60)
    app_log.info("App started at %s", datetime.now().isoformat())
    app_log.info("=" * 60)

    # --- 2. Audit-specific log (system-level, supplements DB audit trail) ---
    setup_file_logger("audit", "audit.log", logging.INFO)
    logging.getLogger("audit").info("Audit log initialized")

    # --- 3. HTTP access log ---
    setup_file_logger("access", "access.log", logging.INFO)
    logging.getLogger("access").info("Access log initialized")

    # --- 3. Redirect root logger to file too ---
    root_logger = logging.getLogger()
    root_logger.setLevel(app_log_level)
    # Avoid duplicate console output
    for h in root_logger.handlers[:]:
        if isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)
    root_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, "flask_app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    root_handler.setFormatter(FORMATTER)
    root_logger.addHandler(root_handler)

    # Silence noisy libs
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return app_log


def configure_test_logging():
    """Minimal logging for tests (console only)."""
    logging.basicConfig(
        level=logging.DEBUG,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        force=True,
    )
