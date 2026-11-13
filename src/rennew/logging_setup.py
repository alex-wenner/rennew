import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> Path:
    log_dir = Path.home() / ".rennew"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "rennew.log"
    root = logging.getLogger("rennew")
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return log_path
