from typing import Protocol

from app.dexpi.schemas import DexpiMappingPreview, DexpiMappingReport
from app.domain.models import EngineeringGraph


class DexpiAdapter(Protocol):
    """Replaceable boundary between EngineeringGraph and future DEXPI implementations."""

    def validate_mappable(self, graph: EngineeringGraph) -> DexpiMappingReport: ...

    def map_supported(self, graph: EngineeringGraph) -> DexpiMappingPreview: ...
