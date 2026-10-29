"""Business logic services."""


class ServiceError(Exception):
    """Raised when a business rule prevents an operation."""

    def __init__(self, message: str, errors: dict | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
