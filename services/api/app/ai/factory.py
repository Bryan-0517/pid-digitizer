from app.ai.errors import ProviderConfigurationError, ProviderNotConfiguredError
from app.ai.mock import MockAIProvider, MockFixture
from app.ai.provider import AIProvider
from app.config import Settings


def create_ai_provider(
    settings: Settings, *, mock_fixtures: dict[str, MockFixture] | None = None
) -> AIProvider:
    if not settings.ai_provider:
        raise ProviderNotConfiguredError()
    if settings.ai_provider == "mock":
        return MockAIProvider(mock_fixtures or {})
    raise ProviderConfigurationError("Configured AI provider is not supported")
