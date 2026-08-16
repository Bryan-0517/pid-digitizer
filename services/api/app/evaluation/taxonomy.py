from app.ai.contracts import AIContract
from app.ai.entity_proposals import EntityCandidate, EntityExtractionProposal

IN_SCOPE_KINDS = {"equipment", "boundary", "instrument"}
UI_TERMS = {
    "button",
    "hollysys",
    "logo",
    "menu",
    "navigation",
    "thinkvision",
    "timestamp",
}


class ProposalTaxonomyDiagnostics(AIContract):
    strict_proposal_count: int
    in_scope_semantic_candidate_ids: list[str]
    out_of_reference_scope_visual_candidate_ids: list[str]
    obvious_ui_or_non_engineering_candidate_ids: list[str]


def classify_proposal_taxonomy(
    proposal: EntityExtractionProposal,
) -> ProposalTaxonomyDiagnostics:
    in_scope = []
    out_of_scope = []
    obvious_ui = []
    for candidate in sorted(proposal.candidates, key=lambda item: item.candidate_id):
        if _is_obvious_ui(candidate):
            obvious_ui.append(candidate.candidate_id)
        elif candidate.kind in IN_SCOPE_KINDS:
            in_scope.append(candidate.candidate_id)
        else:
            out_of_scope.append(candidate.candidate_id)
    return ProposalTaxonomyDiagnostics(
        strict_proposal_count=len(proposal.candidates),
        in_scope_semantic_candidate_ids=in_scope,
        out_of_reference_scope_visual_candidate_ids=out_of_scope,
        obvious_ui_or_non_engineering_candidate_ids=obvious_ui,
    )


def _is_obvious_ui(candidate: EntityCandidate) -> bool:
    values = [candidate.display_name or "", candidate.tag or ""]
    values.extend(item.evidence_text or "" for item in candidate.provenance)
    text = " ".join(values).casefold()
    return candidate.kind == "text" and any(term in text for term in UI_TERMS)
