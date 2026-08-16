from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


IntentName = Literal["neighbors", "upstream", "downstream", "shortest_path", "entity_lookup"]


@dataclass(frozen=True)
class ParsedIntent:
    operation: IntentName
    references: tuple[str, ...]


_PATH_PATTERNS = (
    re.compile(r"^what is the shortest path from\s+(.+?)\s+to\s+(.+?)\??$", re.IGNORECASE),
    re.compile(r"^how is\s+(.+?)\s+connected to\s+(.+?)\??$", re.IGNORECASE),
)
_SINGLE_PATTERNS: tuple[tuple[IntentName, re.Pattern[str]], ...] = (
    ("neighbors", re.compile(r"^what is connected to\s+(.+?)\??$", re.IGNORECASE)),
    ("neighbors", re.compile(r"^show neighbors of\s+(.+?)\??$", re.IGNORECASE)),
    ("upstream", re.compile(r"^what is upstream of\s+(.+?)\??$", re.IGNORECASE)),
    ("downstream", re.compile(r"^what is downstream of\s+(.+?)\??$", re.IGNORECASE)),
    ("entity_lookup", re.compile(r"^find\s+(.+?)\??$", re.IGNORECASE)),
    ("entity_lookup", re.compile(r"^look up\s+(.+?)\??$", re.IGNORECASE)),
)


def resolve_intent(message: str) -> ParsedIntent | None:
    normalized = " ".join(message.strip().split())
    for pattern in _PATH_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match:
            references = tuple(part.strip() for part in match.groups())
            if all(references):
                return ParsedIntent("shortest_path", references)
    for operation, pattern in _SINGLE_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match and match.group(1).strip():
            return ParsedIntent(operation, (match.group(1).strip(),))
    return None
