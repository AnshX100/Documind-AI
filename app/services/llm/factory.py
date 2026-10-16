"""Factory for instantiating LLM providers based on application configuration."""

import logging
from typing import Dict, Any, Optional

from app.services.llm.base import BaseLLMProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)


def get_llm_provider(config: Dict[str, Any]) -> Optional[BaseLLMProvider]:
    """Instantiate and return the configured LLM provider instance.

    Args:
        config (Dict[str, Any]): Flask or dict configuration.

    Returns:
        Optional[BaseLLMProvider]: Provider instance, or None if disabled or unconfigured.
    """
    enabled = config.get("LLM_ENABLED", False)
    if isinstance(enabled, str):
        enabled = enabled.lower() == "true"

    if not enabled:
        logger.info("LLM is disabled via LLM_ENABLED configuration.")
        return None

    provider_name = str(config.get("LLM_PROVIDER", "none")).lower().strip()

    if provider_name in ("openai", "gpt"):
        api_key = config.get("LLM_API_KEY") or config.get("OPENAI_API_KEY")
        model = config.get("LLM_MODEL") or config.get("OPENAI_MODEL", "gpt-4o-mini")
        base_url = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        timeout = int(config.get("LLM_TIMEOUT", 10))
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url, timeout=timeout)

    elif provider_name == "mock":
        return MockLLMProvider()

    else:
        logger.warning(f"Unknown or unconfigured LLM_PROVIDER '{provider_name}'. Falling back to deterministic engine.")
        return None
