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
