"""Errors for development activity persistence and delivery."""


class ActivityLogError(Exception):
    """Base error for development activity log operations."""


class PersistenceError(ActivityLogError):
    """The activity event could not be stored in PostgreSQL."""


class SlackDeliveryError(ActivityLogError):
    """The event was stored but Slack delivery did not succeed."""
