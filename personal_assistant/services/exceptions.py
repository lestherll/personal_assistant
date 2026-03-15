class ServiceError(Exception):
    """Base class for all service-layer errors."""


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""

    def __init__(self, kind: str, name: str) -> None:
        self.kind = kind
        self.name = name
        super().__init__(f"{kind} '{name}' not found")


class AlreadyExistsError(ServiceError):
    """Raised when trying to create a resource that already exists."""

    def __init__(self, kind: str, name: str) -> None:
        self.kind = kind
        self.name = name
        super().__init__(f"{kind} '{name}' already exists")


class ServiceValidationError(ServiceError):
    """Raised when input data fails domain validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class AuthError(ServiceError):
    """Raised when authentication fails (401)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class ForbiddenError(ServiceError):
    """Raised when the user lacks permission (403)."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message)
