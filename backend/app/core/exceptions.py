class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EntityNotFoundException(DomainException):
    """Raised when a requested resource does not exist."""
    pass


class PermissionDeniedException(DomainException):
    """Raised when a user lacks access rights to a resource."""
    pass


class IngestionError(DomainException):
    """Raised when PDF parsing, chunking, or indexing pipeline fails."""
    pass
