"""High-level convenience entrypoints for the public library API."""

from __future__ import annotations

from .orchestrator import Orchestrator
from .settings import Settings
from .state import create_state


def run_task(task: str, project_root: str | None = None, settings: Settings | None = None) -> dict:
    """Run a task through the full orchestration flow and return the final state."""
    runtime_settings = settings or Settings(project_root=project_root)
    state = create_state(task)
    state["project_root"] = runtime_settings.resolved_project_root()
    state["export_enabled"] = runtime_settings.export_enabled
    orchestrator = Orchestrator(
        autonomous_rounds=runtime_settings.autonomous_rounds,
        max_iterations_per_step=runtime_settings.max_iterations_per_step,
    )
    return orchestrator.run(task, state)
