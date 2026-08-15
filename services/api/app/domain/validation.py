from dataclasses import dataclass

from .models import EngineeringGraph


@dataclass(frozen=True)
class GraphValidationWarning:
    code: str
    message: str
    entity_ids: tuple[str, ...]


def duplicate_tag_warnings(graph: EngineeringGraph) -> list[GraphValidationWarning]:
    entities_by_tag: dict[str, list[str]] = {}
    for entity in graph.entities:
        if entity.tag is not None:
            entities_by_tag.setdefault(entity.tag, []).append(entity.id)

    return [
        GraphValidationWarning(
            code="duplicate_tag",
            message=f"tag {tag!r} is used by multiple entities",
            entity_ids=tuple(entity_ids),
        )
        for tag, entity_ids in sorted(entities_by_tag.items())
        if len(entity_ids) > 1
    ]
