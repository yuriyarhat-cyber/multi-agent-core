"""Simple OpenAI Responses API adapter."""

from __future__ import annotations

import logging
import os

from openai import OpenAI


DEFAULT_OPENAI_MODEL = "gpt-5.3-codex"
LOGGER = logging.getLogger(__name__)


def get_openai_api_key() -> str:
    """Return the configured OpenAI API key or raise a clear error."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return api_key


def get_openai_model() -> str:
    """Return the configured OpenAI model name or the default model."""
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def codex_llm(prompt: str) -> str:
    """Send a prompt to the OpenAI Responses API and return plain text."""
    get_openai_api_key()
    model = get_openai_model()
    LOGGER.info("Sending request to OpenAI Responses API with model '%s'", model)
    client = OpenAI()

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
    except Exception as exc:
        LOGGER.error("OpenAI API request failed: %s", exc)
        raise RuntimeError(
            f"OpenAI API request failed: {exc}"
        ) from exc

    output_text = getattr(response, "output_text", "")
    if output_text:
        LOGGER.info("Received text response from OpenAI")
        return output_text

    LOGGER.error("OpenAI API returned no text output")
    raise RuntimeError("OpenAI API request succeeded but returned no text output.")
