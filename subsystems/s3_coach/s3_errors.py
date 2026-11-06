"""
Custom error-handling classes for Subsystem 3 (AI Coach & Data Persistence).
"""


class S3CoachError(Exception):
    """Base exception for all Subsystem 3 errors."""

    def __init__(self, message: str, error_code: str = "E300_GENERAL_ERROR"):
        super().__init__(message)
        self._message: str = ""
        self._error_code: str = ""
        self._setup_error(message, error_code)

    def _setup_error(self, message: str, error_code: str) -> None:
        """Initializes error state."""
        self.message = message
        self.error_code = error_code

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        self._message = value if value else "Unknown S3 error occurred."

    @property
    def error_code(self) -> str:
        return self._error_code

    @error_code.setter
    def error_code(self, value: str) -> None:
        self._error_code = value if value else "E300_GENERAL_ERROR"

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class S3ConfigurationError(S3CoachError):
    """Raised when state initialization or configuration validation fails."""

    def __init__(self, message: str):
        super().__init__(message, error_code="E301_CONFIG_ERROR")


class S3APIError(S3CoachError):
    """Raised when an external LLM provider (OpenAI/NVIDIA) fails or times out."""

    def __init__(self, message: str):
        super().__init__(message, error_code="E302_API_ERROR")


class S3DatabaseError(S3CoachError):
    """Raised when a database persistence or query operation fails."""

    def __init__(self, message: str):
        super().__init__(message, error_code="E303_DB_ERROR")