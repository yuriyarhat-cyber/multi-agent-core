"""Mock LLM integration point.

Replace ``codex_llm`` later with a real provider if you want richer behavior.
The rest of the library treats this as a simple text-in, text-out function.
"""

from __future__ import annotations


def codex_llm(prompt: str) -> str:
    """Return a deterministic mock response for offline development."""
    normalized = " ".join(prompt.strip().split())
    if not normalized:
        return "mock-response: empty prompt"
    return f"mock-response: {normalized[:120]}"
