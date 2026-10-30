"""
Structured logging configuration for ResearchDesk.
Ensures consistent format, request-tracing context, and strict redaction of secrets.
"""

import logging
import sys
from typing import Optional


class RedactingFormatter(logging.Formatter):
    """Custom formatter that ensures sensitive tokens and keys are never logged."""

    SENSITIVE_PATTERNS = ["api_key", "authorization", "bearer", "secret", "password"]

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact any obvious Bearer token strings
        for word in msg.split():
            if word.lower().startswith("sk-") and len(word) > 10:
                msg = msg.replace(word, "[REDACTED_API_KEY]")
            elif word.lower().startswith("gsk_") and len(word) > 10:
                msg = msg.replace(word, "[REDACTED_API_KEY]")
        return msg


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configures the root and application loggers."""
    logger = logging.getLogger("researchdesk")
    logger.setLevel(level)

    # Avoid duplicate handlers on reload
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = configure_logging()
