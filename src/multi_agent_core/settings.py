"""Small settings helpers for high-level library usage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    """Simple runtime settings for a multi-agent-core session."""

    project_root: str | None = None
    autonomous_rounds: int = 2
    max_iterations_per_step: int = 3
    export_enabled: bool = False

    def resolved_project_root(self) -> str:
        """Return the effective project root for this run."""
        return self.project_root or str(Path.cwd())

