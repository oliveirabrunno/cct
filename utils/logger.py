import os
import sys
from loguru import logger

_configured = False


def get_logger(name: str):
    global _configured
    if not _configured:
        level = os.getenv("LOG_LEVEL", "INFO")
        logger.remove()
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> — {message}",
            colorize=True,
        )
        logger.add(
            "logs/cafecomtenis.log",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} — {message}",
        )
        _configured = True
    return logger.bind(name=name)
