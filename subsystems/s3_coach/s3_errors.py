"""
Custom error-handling classes for Subsystem 3 (AI Coach & Data Persistence).
"""

import logging
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger("s3_coach")


class S3CoachError(Exception):
    """Base exception for all Subsystem 3 errors."""

    def __init__(self, message: str, error_code: str = "E300_GENERAL_ERROR") -> None:
        self._message: str = ""
        self._error_code: str = ""
        self._timestamp: str = ""
        self._setup_error(message, error_code)
        super().__init__(str(self))

    def _setup_error(self, message: str, error_code: str) -> None:
        """Initializes error state and logs the occurrence with an ISO 8601 timestamp."""
        self.message = message
        self.error_code = error_code
        self._timestamp = datetime.now(timezone.utc).isoformat()
        logger.error("[%s] %s: %s", self._timestamp, self.error_code, self.message)

    @property
    def message(self) -> str:
        """Getter for the error message."""
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        """Setter validating the error message."""
        self._message = (
            value.strip() if value and value.strip() else "Unknown S3 error occurred."
        )

    @property
    def error_code(self) -> str:
        """Getter for the standardized error code."""
        return self._error_code

    @error_code.setter
    def error_code(self, value: str) -> None:
        """Setter validating the standardized error code."""
        self._error_code = (
            value.strip() if value and value.strip() else "E300_GENERAL_ERROR"
        )

    @property
    def timestamp(self) -> str:
        """Getter for the UTC ISO-8601 timestamp when the error was raised."""
        return self._timestamp

    def to_dict(self) -> Dict[str, str]:
        """Serialize the exception state for Flask JSON error responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class S3ConfigurationError(S3CoachError):
    """Raised when state initialization or configuration validation fails."""

    def __init__(
        self, message: str, error_code: str = "E301_CONFIG_ERROR"
    ) -> None:
        super().__init__(message, error_code=error_code)


class S3APIError(S3CoachError):
    """Raised when an external LLM provider (OpenAI/NVIDIA) fails or times out."""

    def __init__(self, message: str, error_code: str = "E302_API_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class S3DatabaseError(S3CoachError):
    """Raised when a database persistence or query operation fails."""

    def __init__(self, message: str, error_code: str = "E303_DB_ERROR") -> None:
        super().__init__(message, error_code=error_code)