from app.dexpi.export_schemas import ConversionReport
from app.dexpi.pydexpi_v1_2_adapter import ExportArtifact, PydexpiV12Adapter
from app.dexpi.v01_adapter import VersionNeutralDexpiAdapter
from app.domain.models import EngineeringGraph


class DexpiExportService:
    def __init__(
        self,
        preflight_adapter: VersionNeutralDexpiAdapter | None = None,
        pydexpi_adapter: PydexpiV12Adapter | None = None,
    ):
        self.preflight_adapter = preflight_adapter or VersionNeutralDexpiAdapter()
        self.pydexpi_adapter = pydexpi_adapter or PydexpiV12Adapter()

    def plan(self, graph: EngineeringGraph) -> ConversionReport:
        preflight = self.preflight_adapter.validate_mappable(graph)
        return self.pydexpi_adapter.plan(graph, preflight)

    def export(self, graph: EngineeringGraph) -> ExportArtifact:
        plan = self.plan(graph)
        return self.pydexpi_adapter.export(graph, plan)
