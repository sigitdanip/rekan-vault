from abc import ABC, abstractmethod
from typing import Any

from rekanvault.contracts.documents import NormalizedDocument, SourceProvider


class BaseConnector(ABC):
    def __init__(self, source_id: str, config: dict[str, Any]) -> None:
        self.source_id = source_id
        self.config = config

    @property
    @abstractmethod
    def provider(self) -> SourceProvider:
        pass

    @abstractmethod
    async def scan(self) -> list[NormalizedDocument]:
        """Full inventory scan of the connector source."""
        pass

    @abstractmethod
    async def fetch_changes(self, cursor: str | None = None) -> dict[str, Any]:
        """Incremental change feed processing."""
        pass

    @abstractmethod
    async def reconcile(self) -> dict[str, Any]:
        """Reconcile expected vs actual state."""
        pass
