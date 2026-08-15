from app.ai.errors import ProviderConfigurationError, ProviderNotConfiguredError
from app.ai.mock import MockAIProvider, MockFixture
from app.ai.openai_provider import OpenAIProvider
from app.ai.provider import AIProvider
from app.config import Settings


def create_ai_provider(
    settings: Settings, *, mock_fixtures: dict[str, MockFixture] | None = None
) -> AIProvider:
    if not settings.ai_provider:
        raise ProviderNotConfiguredError()
    if settings.ai_provider == "mock":
        return MockAIProvider(mock_fixtures or {})
    if settings.ai_provider == "openai":
        if not settings.ai_model or not settings.ai_api_key:
            raise ProviderConfigurationError(
                "OpenAI provider requires AI_MODEL and AI_API_KEY"
            )
        return OpenAIProvider(api_key=settings.ai_api_key, model=settings.ai_model)
    raise ProviderConfigurationError("Configured AI provider is not supported")
