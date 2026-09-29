"""Domain-specific exception hierarchy.

A single base exception (:class:`ChatbotError`) lets callers catch every
application-level failure with one ``except`` clause, while the concrete
subclasses allow precise handling where it matters (missing files, bad data,
LLM/API problems).
"""

from __future__ import annotations


class ChatbotError(Exception):
    """Base class for all errors raised by this application."""


class ConfigurationError(ChatbotError):
    """Raised when required configuration (e.g. an API key) is missing."""


class DataError(ChatbotError):
    """Base class for problems with the underlying CSV data."""


class DataFileNotFoundError(DataError):
    """Raised when a required CSV data file does not exist."""


class DataValidationError(DataError):
    """Raised when a CSV row cannot be parsed into a valid domain model."""


class DealerNotFoundError(ChatbotError):
    """Raised when a car references a dealer id that does not exist."""


class LLMError(ChatbotError):
    """Raised when the language-model provider fails or misbehaves."""
