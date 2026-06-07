"""Provider 工厂。"""

from __future__ import annotations

from ..config import Config
from .base import Provider


def build_provider(config: Config) -> Provider:
    if config.provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=config.resolved_model(),
            max_tokens=config.max_tokens,
        )
    elif config.provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=config.openai_api_key,
            model=config.resolved_model(),
            base_url=config.openai_base_url,
            max_tokens=config.max_tokens,
        )
    raise ValueError(f"未知 provider: {config.provider}")


__all__ = ["Provider", "build_provider"]
