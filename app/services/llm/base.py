"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers in DocuMind AI."""

    @abstractmethod
    def generate_response(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Generate a natural language response given prompt text and system instructions.

        Args:
            prompt (str): User prompt with verified context.
            system_instruction (str): Controlled system directive.

        Returns:
            Optional[str]: LLM generated string response, or None if call fails/unconfigured.
        """
        pass
