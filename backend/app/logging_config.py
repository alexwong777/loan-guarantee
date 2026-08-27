import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.getenv("LOG_DIR", "/app/logs")


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("guarantee_studio")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, "backend.log"), maxBytes=5_000_000, backupCount=3
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # Falls back to console-only logging if the log directory isn't writable.
        logger.warning("Could not open %s for file logging; console only.", LOG_DIR)

    return logger


logger = _build_logger()
