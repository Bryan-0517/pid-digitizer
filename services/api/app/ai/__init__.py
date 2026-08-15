"""Vendor-neutral multimodal extraction provider boundary."""

from app.ai.factory import create_ai_provider
from app.ai.mock import MockAIProvider, MockFixture
from app.ai.openai_provider import OpenAIProvider
from app.ai.provider import AIProvider, execute_extraction

__all__ = [
    "AIProvider",
    "MockAIProvider",
    "MockFixture",
    "OpenAIProvider",
    "create_ai_provider",
    "execute_extraction",
]
