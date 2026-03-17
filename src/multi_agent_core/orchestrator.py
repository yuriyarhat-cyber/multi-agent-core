"""Planner-builder-critic orchestration flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .agents import Builder, Critic, Planner
from .state import REQUIRED_STATE_KEYS, create_state


class Orchestrator:
    """Run a small multi-agent workflow over shared state."""

    def __init__(
        self,
        planner: Planner | None = None,
        builder: Builder | None = None,
        critic: Critic | None = None,
        max_iterations_per_step: int = 3,
    ) -> None:
        self.planner = planner or Planner()
        self.builder = builder or Builder()
        self.critic = critic or Critic()
        self.max_iterations_per_step = max(1, min(max_iterations_per_step, 3))

    def run(self, task: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
        shared_state = create_state(task) if state is None else state
        self._ensure_required_keys(shared_state, task)

        if not shared_state["plan"].get("steps"):
            shared_state["plan"] = self.planner.run(shared_state)

        for step in shared_state["plan"].get("steps", []):
            shared_state["current_step"] = step
            shared_state["critique"] = {}

            for attempt in range(1, self.max_iterations_per_step + 1):
                shared_state["_attempt"] = attempt
                shared_state["build"] = self.builder.run(shared_state)
                shared_state["critique"] = self.critic.run(shared_state)
                self._save_history(shared_state, step, attempt)

                if shared_state["critique"].get("status") == "pass":
                    break

        shared_state.pop("_attempt", None)
        return shared_state

    def _ensure_required_keys(self, state: dict[str, Any], task: str) -> None:
        defaults = create_state(task)
        for key in REQUIRED_STATE_KEYS:
            state.setdefault(key, defaults[key])
        state["task"] = task

    def _save_history(self, state: dict[str, Any], step: str, attempt: int) -> None:
        state["history"].append(
            {
                "step": step,
                "attempt": attempt,
                "build": deepcopy(state["build"]),
                "critique": deepcopy(state["critique"]),
            }
        )
