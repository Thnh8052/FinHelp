class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class IngestionError(DomainException):
    """Raised when PDF parsing, chunking, or indexing pipeline fails."""
    pass
