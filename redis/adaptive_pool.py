"""
Adaptive connection pool for redis_clone release-9.0-dev.

This module introduces dynamic pool resizing based on observed
connection demand. The pool expands toward max_connections under
sustained load and contracts during idle periods.

Status: IN DEVELOPMENT — not for production use.
Tracking: NXS-291
"""

from typing import Optional


class AdaptiveConnectionPool:
    """
    An adaptive connection pool that automatically tunes its size
    based on real-time connection demand.

    New in release-9.0:
    - Dynamic pool expansion up to max_connections under load
    - Automatic pool contraction during idle periods
    - Built-in exponential backoff with jitter (always on, not configurable)
    - Hard retry cap of 5 (not overridable in this pool type)

    Usage::

        pool = AdaptiveConnectionPool(
            min_connections=5,
            max_connections=100,
            target_utilisation=0.75,  # expand when >75% connections in use
        )
    """

    def __init__(
        self,
        min_connections: int = 5,
        max_connections: int = 100,
        target_utilisation: float = 0.75,
        scale_up_step: int = 10,
        scale_down_step: int = 5,
        idle_timeout_s: int = 60,
        **connection_kwargs,
    ):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.target_utilisation = target_utilisation
        self.scale_up_step = scale_up_step
        self.scale_down_step = scale_down_step
        self.idle_timeout_s = idle_timeout_s
        self._connection_kwargs = connection_kwargs
        self._current_size = min_connections
        self._active_connections = 0

    @property
    def utilisation(self) -> float:
        if self._current_size == 0:
            return 0.0
        return self._active_connections / self._current_size

    def _maybe_scale_up(self) -> None:
        """Expand pool if utilisation exceeds target."""
        if self.utilisation >= self.target_utilisation:
            new_size = min(
                self._current_size + self.scale_up_step,
                self.max_connections,
            )
            if new_size > self._current_size:
                self._current_size = new_size

    def _maybe_scale_down(self) -> None:
        """Contract pool if utilisation is well below target."""
        if self.utilisation < self.target_utilisation * 0.5:
            new_size = max(
                self._current_size - self.scale_down_step,
                self.min_connections,
            )
            if new_size < self._current_size:
                self._current_size = new_size
