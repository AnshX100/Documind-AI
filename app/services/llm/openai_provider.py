"""OpenAI/OpenAI-compatible LLM Provider implementation."""

import logging
import json
from typing import Optional
import requests

from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Provider for OpenAI / OpenAI-compatible REST API endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 10
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate_response(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Generate response via OpenAI Chat Completions REST API.

        Args:
            prompt (str): User prompt text with evidence.
            system_instruction (str): Controlled system instructions.

        Returns:
            Optional[str]: Generated answer prose, or None if error/unconfigured.
        """
        if not self.api_key or self.api_key.strip() in ("", "none", "YOUR_OPENAI_API_KEY"):
            logger.warning("OpenAI API key is missing or unconfigured. Falling back to deterministic engine.")
            return None

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.error(f"OpenAI API error HTTP status {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.get_json() if hasattr(resp, "get_json") else resp.json()
            choices = data.get("choices", [])
            if not choices:
                logger.warning("OpenAI API returned empty choices array.")
                return None

            content = choices[0].get("message", {}).get("content", "").strip()
            if not content:
                logger.warning("OpenAI API returned empty content text.")
                return None

            return content

        except requests.exceptions.Timeout:
            logger.warning(f"OpenAI API call timed out after {self.timeout}s. Falling back to deterministic engine.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error communicating with OpenAI API: {e}")
            return None
