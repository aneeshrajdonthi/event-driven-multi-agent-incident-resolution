"""Unified LLM client supporting vLLM (OpenAI-compatible) and Google Gemini."""

from __future__ import annotations

import json
import logging
from typing import Any, Type, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Retry on transient HTTP / network errors
_RETRY_KWARGS: dict[str, Any] = dict(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


class LLMClient:
    """Thin async wrapper around vLLM and Gemini APIs."""

    def __init__(self) -> None:
        settings = get_settings()
        self._vllm_url: str = settings.VLLM_API_URL
        self._gemini_key: str = settings.GEMINI_API_KEY
        self._model: str = settings.MODEL_NAME
        self._http: httpx.AsyncClient = httpx.AsyncClient(timeout=120.0)
        self._gemini_model: Any | None = None

    # ----- internal helpers ------------------------------------------------

    def _use_gemini(self) -> bool:
        return bool(self._gemini_key)

    async def _ensure_gemini(self) -> Any:
        if self._gemini_model is None:
            import google.generativeai as genai  # type: ignore[import-untyped]

            genai.configure(api_key=self._gemini_key)
            self._gemini_model = genai.GenerativeModel(self._model)
        return self._gemini_model

    # ----- public API ------------------------------------------------------

    @retry(**_RETRY_KWARGS)
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a text completion from the configured LLM backend."""

        if self._use_gemini():
            model = await self._ensure_gemini()
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = await model.generate_content_async(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return response.text  # type: ignore[return-value]

        # vLLM / OpenAI-compatible endpoint
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = await self._http.post(
            f"{self._vllm_url}/chat/completions", json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @retry(**_RETRY_KWARGS)
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a completion and parse it into a Pydantic model."""

        raw = await self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Attempt to extract JSON from the raw response
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON block inside markdown fences
            import re

            match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group(1).strip())
            else:
                raise

        return response_model.model_validate(parsed)

    async def close(self) -> None:
        """Clean up the underlying HTTP client."""
        await self._http.aclose()
