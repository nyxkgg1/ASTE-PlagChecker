
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class OllamaServiceError(Exception):
    """Raised when the local Ollama service cannot complete a request."""


def generate_explanation(
    *,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int | None = None,
    think: bool | None = None,
) -> str:
    """
    Generate an explanation using the locally installed Ollama model.

    This function is intended for explaining existing analysis results.
    It must not be used to calculate or modify detector scores.
    """

    if not system_prompt.strip():
        raise ValueError("System prompt cannot be empty.")

    if not user_prompt.strip():
        raise ValueError("User prompt cannot be empty.")

    base_url = settings.ollama_base_url.rstrip("/")
    endpoint = f"{base_url}/api/chat"

    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "temperature": 0.2,
        },
    }
    if think is not None:
        payload["think"] = think

    try:
        response = httpx.post(
            endpoint,
            json=payload,
            timeout=(
    timeout_seconds
    if timeout_seconds is not None
    else settings.ollama_timeout_seconds
),
        )

        response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise OllamaServiceError(
            "Ollama request timed out. The local model may need "
            "more time to respond."
        ) from exc

    except httpx.HTTPStatusError as exc:
        error_details = exc.response.text[:500]

        raise OllamaServiceError(
            f"Ollama returned HTTP {exc.response.status_code}: "
            f"{error_details}"
        ) from exc

    except httpx.RequestError as exc:
        raise OllamaServiceError(
            "Could not connect to Ollama. Check that the local "
            "Ollama service is running."
        ) from exc

    try:
        data = response.json()
        explanation = data["message"]["content"]

    except (ValueError, KeyError, TypeError) as exc:
        raise OllamaServiceError(
            "Ollama returned an unexpected response format."
        ) from exc

    if not isinstance(explanation, str) or not explanation.strip():
        raise OllamaServiceError(
            "Ollama returned an empty explanation."
        )

    return explanation.strip()
