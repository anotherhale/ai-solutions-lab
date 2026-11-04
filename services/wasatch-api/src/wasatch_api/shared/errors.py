"""Application errors independent of FastAPI."""


class NotFoundError(LookupError):
    """A business record does not exist."""


class InvalidParameterError(ValueError):
    """A query or path parameter is not acceptable."""
