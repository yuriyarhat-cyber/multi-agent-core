"""High-level convenience entrypoints for the public library API."""

from __future__ import annotations

from pathlib import Path

from .orchestrator import Orchestrator
from .state import create_state


def run_task(task: str, project_root: str | None = None) -> dict:
    """Run a task through the full orchestration flow and return the final state."""
    state = create_state(task)
    state["project_root"] = project_root or str(Path.cwd())
    orchestrator = Orchestrator()
    return orchestrator.run(task, state)
