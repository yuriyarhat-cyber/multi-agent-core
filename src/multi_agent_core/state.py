"""Shared state helpers."""

from __future__ import annotations

from typing import Any


REQUIRED_STATE_KEYS = (
    "task",
    "routing",
    "executed_flow",
    "plan",
    "current_step",
    "build",
    "critique",
    "history",
)


def create_state(task: str) -> dict[str, Any]:
    """Create the shared state used by the orchestrator and agents."""
    return {
        "task": task,
        "routing": {},
        "executed_flow": [],
        "plan": {"steps": [], "summary": ""},
        "current_step": None,
        "build": {},
        "critique": {},
        "history": [],
    }
