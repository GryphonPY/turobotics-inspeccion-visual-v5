from __future__ import annotations

from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class LatestValue(Generic[T]):
    """Thread-safe single-slot store that deliberately drops stale values."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._version = 0
        self._value: T | None = None

    def publish(self, value: T) -> int:
        with self._lock:
            self._version += 1
            self._value = value
            return self._version

    def read(self, after_version: int = -1) -> tuple[int, T | None]:
        with self._lock:
            if self._value is None or self._version <= after_version:
                return self._version, None
            return self._version, self._value

    def clear(self) -> None:
        with self._lock:
            self._version += 1
            self._value = None
