"""Mock LLM Provider for unit testing and offline development."""

import logging
from typing import Optional
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider returning deterministic prose responses."""

    def __init__(self, mock_response: Optional[str] = None, should_raise: bool = False) -> None:
        self.mock_response = mock_response
        self.should_raise = should_raise
        self.last_prompt: Optional[str] = None
        self.last_system_instruction: Optional[str] = None

    def generate_response(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Record prompt and return mocked response."""
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction

        if self.should_raise:
            raise RuntimeError("Mock LLM Provider simulated failure.")

        if self.mock_response is not None:
            return self.mock_response

        # Default mock response synthesis
        return "Based on your verified financial records, here is your requested information."
