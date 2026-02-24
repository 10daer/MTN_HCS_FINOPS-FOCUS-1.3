"""
Abstract base mapper.

Every mapper implements ``map_record`` (single item) and ``map_many`` (batch).
This enforces a consistent contract across all transformation strategies.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

SourceT = TypeVar("SourceT", bound=BaseModel)
TargetT = TypeVar("TargetT", bound=BaseModel)


class BaseMapper(ABC, Generic[SourceT, TargetT]):
    """Contract that every data mapper must fulfil."""

    @abstractmethod
    def map_record(self, source: SourceT) -> TargetT:
        """
        Transform a single source record into the target format.

        Raises:
            TransformationException: If the mapping cannot be completed.
        """
        ...

    def map_many(self, sources: list[SourceT]) -> list[TargetT]:
        """
        Transform a batch of source records.

        Override for optimised bulk behaviour; default iterates one-by-one.
        """
        return [self.map_record(s) for s in sources]
