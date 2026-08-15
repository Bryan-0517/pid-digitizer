from __future__ import annotations

import asyncio
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.ai.contracts import StructuredExtractionRequest, StructuredExtractionResponse
from app.ai.errors import AIProviderError, ProviderRequestError, ProviderTimeoutError

OutputT = TypeVar("OutputT", bound=BaseModel)


class AIProvider(Protocol):
    async def extract(
        self, request: StructuredExtractionRequest, output_type: type[OutputT]
    ) -> StructuredExtractionResponse[OutputT]: ...


async def execute_extraction(
    provider: AIProvider,
    request: StructuredExtractionRequest,
    output_type: type[OutputT],
    *,
    timeout_seconds: float = 60,
) -> StructuredExtractionResponse[OutputT]:
    try:
        return await asyncio.wait_for(
            provider.extract(request, output_type), timeout=timeout_seconds
        )
    except TimeoutError as exc:
        raise ProviderTimeoutError() from exc
    except AIProviderError:
        raise
    except Exception as exc:
        raise ProviderRequestError() from exc
