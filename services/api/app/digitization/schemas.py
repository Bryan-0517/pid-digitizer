from app.ai.contracts import AIContract, ProviderMetadata
from app.ai.entity_proposals import EntityExtractionProposal
from app.ai.topology_proposals import TopologyExtractionProposal


class DigitizationProposalResponse(AIContract):
    document_id: str
    page_id: str
    entities: EntityExtractionProposal
    topology: TopologyExtractionProposal
    entity_provider_metadata: ProviderMetadata
    topology_provider_metadata: ProviderMetadata
    warnings: list[str]
    canonical_graph_mutated: bool = False
