from abc import ABC, abstractmethod
from typing import Any

from .schemas import NormalizedNotice


class SourceAdapter(ABC):
    """Adapter contract for an approved, configured public source."""

    def __init__(self, source_url: str, timeout_seconds: float = 10.0):
        self.source_url = source_url
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def parse(self, body: str, response_url: str | None = None) -> list[NormalizedNotice]:
        raise NotImplementedError

    def fetch(self) -> list[NormalizedNotice]:
        raise NotImplementedError("Network fetching is implemented by concrete adapters.")

