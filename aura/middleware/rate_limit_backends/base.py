"""Abstract interface for rate-limit storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RateLimitBackend(ABC):
    """Abstract base class for rate-limit backend implementations.

    Concrete backends (in-memory, Redis, etc.) must implement :meth:`acquire`
    so middleware and guards stay storage-agnostic.
    """

    @abstractmethod
    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: float,
    ) -> tuple[bool, int]:
        """Try to acquire a rate-limit slot for *key*.

        Args:
            key: Identifier for the client or resource being limited.
            max_requests: Maximum allowed requests in the sliding window.
            window_seconds: Length of the sliding window in seconds.

        Returns:
            A tuple ``(allowed, remaining)`` where *allowed* is ``True`` when
            the request may proceed and *remaining* is the number of requests
            still available in the current window (``0`` when denied).
        """
        ...
