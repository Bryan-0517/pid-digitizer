from enum import StrEnum


class AIErrorCode(StrEnum):
    NOT_CONFIGURED = "provider_not_configured"
    CONFIGURATION = "provider_configuration_error"
    REQUEST_FAILED = "provider_request_failed"
    TIMEOUT = "provider_timeout"
    MALFORMED_OUTPUT = "malformed_structured_output"
    UNSUPPORTED_INPUT = "unsupported_media_input"
    PARSING_FAILED = "response_parsing_failed"


class AIProviderError(Exception):
    def __init__(self, code: AIErrorCode, message: str):
        self.code = code
        super().__init__(message)


class ProviderNotConfiguredError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.NOT_CONFIGURED, "AI provider is not configured")


class ProviderConfigurationError(AIProviderError):
    def __init__(self, message: str = "AI provider configuration is invalid") -> None:
        super().__init__(AIErrorCode.CONFIGURATION, message)


class ProviderRequestError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.REQUEST_FAILED, "AI provider request failed")


class ProviderTimeoutError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.TIMEOUT, "AI provider request timed out")


class MalformedStructuredOutputError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.MALFORMED_OUTPUT, "AI provider returned malformed structured output")


class ResponseParsingError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.PARSING_FAILED, "AI provider response could not be parsed")


class UnsupportedMediaInputError(AIProviderError):
    def __init__(self) -> None:
        super().__init__(AIErrorCode.UNSUPPORTED_INPUT, "AI provider input media is unsupported")
