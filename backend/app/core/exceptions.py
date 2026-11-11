class DomainException(Exception):
    """A failure the interface must explain. `code` names the sentence (see app/core/error_codes.py), `params` fill its blanks."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


class IngestionError(DomainException):
    """Raised when PDF parsing, chunking, or indexing pipeline fails."""
    pass
