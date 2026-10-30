"""
LLM Service client using the official OpenAI SDK.
Works seamlessly across OpenAI, Groq, OpenRouter, and Gemini OpenAI-compatible endpoints.
Provides structured JSON extraction, timeout protection, and exponential backoff retry.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from backend.config import settings
from backend.utils.logging_config import logger


class LLMService:
    """Wrapper around LLM providers with retry, structured JSON, and fallback logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or settings.effective_api_key
        self.model = model or settings.llm_model
        self.base_url = base_url or settings.llm_base_url
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.client: Optional[OpenAI] = None

        if self.api_key and not self.api_key.startswith("your_"):
            try:
                # Custom base_url handling (e.g. Groq, OpenRouter, local vLLM)
                if not self.base_url and settings.llm_provider.lower() == "groq":
                    self.base_url = "https://api.groq.com/openai/v1"
                elif not self.base_url and settings.llm_provider.lower() == "gemini":
                    self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=settings.llm_timeout_seconds,
                    max_retries=settings.max_tool_retries,
                )
                logger.info(
                    f"Initialized LLM client (provider: {settings.llm_provider}, model: {self.model})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Executes a chat completion call with retries and timing."""
        if not self.client:
            raise RuntimeError(
                "LLM service is not configured. Please supply a valid LLM API key in .env"
            )

        temp = temperature if temperature is not None else self.temperature
        retries = settings.max_tool_retries
        backoff = 1.5

        for attempt in range(retries + 1):
            try:
                start_time = time.time()
                kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": settings.llm_max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                duration = time.time() - start_time
                content = response.choices[0].message.content or ""
                logger.info(
                    f"LLM completion succeeded in {duration:.2f}s (tokens: ~{len(content)//4})"
                )
                return content.strip()

            except RateLimitError as e:
                logger.warning(f"RateLimitError on attempt {attempt+1}/{retries+1}: {e}")
                if attempt == retries:
                    raise
                time.sleep(backoff * (2 ** attempt))
            except APITimeoutError as e:
                logger.warning(f"APITimeoutError on attempt {attempt+1}/{retries+1}: {e}")
                if attempt == retries:
                    raise
                time.sleep(backoff * (2 ** attempt))
            except APIError as e:
                logger.error(f"APIError from LLM provider: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in LLM call: {e}")
                raise

        raise RuntimeError("LLM request failed after maximum retry attempts.")

    def generate_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes an LLM call expecting a JSON object.
        Tries json_object mode, with robust regex fallback if markdown fences are returned.
        """
        # Append instruction ensuring strict JSON
        enhanced_messages = list(messages)
        if not any("json" in m.get("content", "").lower() for m in enhanced_messages):
            enhanced_messages[-1]["content"] += "\nRespond ONLY in valid, parseable JSON."

        raw = self.generate_chat(
            enhanced_messages,
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Attempt to extract JSON from markdown code block ```json ... ```
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Find first { and last }
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start : end + 1])
            raise ValueError(f"LLM response could not be parsed as JSON: {raw[:200]}...")


_llm_instance: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Returns singleton instance of the LLM service."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance
