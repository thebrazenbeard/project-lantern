from __future__ import annotations

from ._store_base import StoreBase
from ._store_commands import CommandsMixin
from ._store_portability import PortabilityMixin
from ._store_projection import ProjectionMixin
from ._store_types import ConflictError, LanternError, OperationResult, ValidationError


class LanternStore(PortabilityMixin, CommandsMixin, ProjectionMixin, StoreBase):
    pass


__all__ = [
    "ConflictError",
    "LanternError",
    "LanternStore",
    "OperationResult",
    "ValidationError",
]
