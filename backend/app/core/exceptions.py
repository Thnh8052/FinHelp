class DomainException(Exception):
    """A failure the interface must explain. `code` names the sentence (see app/core/error_codes.py), `params` fill its blanks."""

    status_code = 400

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


class ServiceUnavailableError(DomainException):
    """A service the request depends on did not answer (the remote GPU worker): 503, and the interface asks to try again later."""

    status_code = 503


class IngestionError(DomainException):
    """Raised when PDF parsing, chunking, or indexing pipeline fails."""
    pass
