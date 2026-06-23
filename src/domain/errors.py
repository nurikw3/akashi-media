"""Domain-level errors. Pure — carry meaning, not transport concerns."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class PublishError(DomainError):
    """A channel publish attempt failed."""


class ContentAdaptationError(DomainError):
    """The content adapter (LLM) failed to produce adapted text."""


class UnknownChannelError(DomainError):
    """No publisher is registered for the requested channel."""
