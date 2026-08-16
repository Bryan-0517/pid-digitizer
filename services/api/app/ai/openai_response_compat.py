from __future__ import annotations

import inspect
from typing import Any


class UnsupportedOpenAIResponseWrapperError(RuntimeError):
    pass


def inspect_response_json(response_wrapper: Any) -> dict[str, Any]:
    """Read diagnostics JSON through the wrapper's public underlying HTTP response."""
    http_response = getattr(response_wrapper, "http_response", None)
    json_method = getattr(http_response, "json", None)
    if not callable(json_method):
        raise UnsupportedOpenAIResponseWrapperError(
            "OpenAI raw response wrapper has no supported http_response.json() interface"
        )
    payload = json_method()
    return payload if isinstance(payload, dict) else {}


async def parse_typed_response(response_wrapper: Any) -> Any:
    """Run the SDK's typed parser across synchronous and asynchronous wrapper generations."""
    parse_method = getattr(response_wrapper, "parse", None)
    if not callable(parse_method):
        raise UnsupportedOpenAIResponseWrapperError(
            "OpenAI raw response wrapper has no supported parse() interface"
        )
    parsed = parse_method()
    return await parsed if inspect.isawaitable(parsed) else parsed
