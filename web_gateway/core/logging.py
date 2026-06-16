import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import settings


def setup_logging():
    settings.log_path.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.log_path / "app.log",
        maxBytes=5_242_880,
        backupCount=3,
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
