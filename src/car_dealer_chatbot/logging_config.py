"""Centralised logging configuration.

Keeping logging setup in one place ensures every entry point (CLI, Streamlit,
tests) produces consistent, structured output and honours the configured level.
"""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once.

    Args:
        level: Logging level name (e.g. ``"INFO"``). Unknown names fall back to
            ``INFO`` rather than raising, so a typo never crashes the app.
    """
    global _configured
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    # Silence the very chatty HTTP client used by the OpenAI SDK unless the user
    # explicitly asked for DEBUG output.
    if numeric_level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, configuring logging on first use.

    Args:
        name: Logger name, conventionally ``__name__`` of the calling module.

    Returns:
        A ready-to-use :class:`logging.Logger`.
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
