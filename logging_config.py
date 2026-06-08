

import logging
import logging.handlers
from pathlib import Path



LOG_FILE =  "trading_bot.log"

_configured = False


def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """
    Configure root logger with:
      - Console handler  : INFO and above, human-readable
      - File handler     : DEBUG and above, timestamped, rotating (5 MB × 3 backups)

    Safe to call multiple times; only configures once.
    """
    global _configured
    if _configured:
        return logging.getLogger("trading_bot")



    root = logging.getLogger("trading_bot")
    root.setLevel(logging.DEBUG)

    # ── Console handler ──────────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))

    # ── Rotating file handler ─────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root.addHandler(console)
    root.addHandler(file_handler)

    _configured = True
    return root