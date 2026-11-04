"""Application errors independent of FastAPI."""


class NotFoundError(LookupError):
    """A business record does not exist."""


class InvalidParameterError(ValueError):
    """A query or path parameter is not acceptable."""


class UnauthenticatedError(PermissionError):
    """The caller did not present an active laboratory actor."""


class AuthorizationDenied(PermissionError):
    """The laboratory actor is not allowed to perform the action."""


class ProviderConfigurationError(RuntimeError):
    """The selected model provider cannot be constructed."""
