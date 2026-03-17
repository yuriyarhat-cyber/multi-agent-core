"""Planner-builder-critic orchestration flow."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from .agents import Builder, Critic, Planner, ResearchCritic
from .router import Router
from .state import REQUIRED_STATE_KEYS, create_state


LOGGER = logging.getLogger(__name__)


class Orchestrator:
    """Run a small multi-agent workflow over shared state."""

    def __init__(
        self,
        router: Router | None = None,
        planner: Planner | None = None,
        builder: Builder | None = None,
        critic: Critic | None = None,
        research_critic: ResearchCritic | None = None,
        max_iterations_per_step: int = 3,
    ) -> None:
        self.router = router or Router()
        self.planner = planner or Planner()
        self.builder = builder or Builder()
        self.critic = critic or Critic()
        self.research_critic = research_critic or ResearchCritic()
        self.max_iterations_per_step = max(1, min(max_iterations_per_step, 3))

    def run(self, task: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run the full planner, builder, and critic loop for a task."""
        shared_state = create_state(task) if state is None else state
        self._ensure_required_keys(shared_state, task)

        if not shared_state["routing"].get("task_type"):
            shared_state["routing"] = self.router.route(task)
            LOGGER.info("Router task type: %s", shared_state["routing"].get("task_type"))
            LOGGER.info("Router reason: %s", shared_state["routing"].get("reason"))

        shared_state["executed_flow"] = list(shared_state["routing"].get("suggested_flow", []))
        LOGGER.info("Executing flow: %s", " -> ".join(shared_state["executed_flow"]))

        if "planner" in shared_state["executed_flow"] and not shared_state["plan"].get("steps"):
            LOGGER.info("Agent running: Planner")
            shared_state["plan"] = self.planner.run(shared_state)
            self._save_history(
                state=shared_state,
                agent_name="planner",
                step=None,
                attempt=1,
                result=shared_state["plan"],
            )

        step_flow = [agent_name for agent_name in shared_state["executed_flow"] if agent_name != "planner"]

        for step in shared_state["plan"].get("steps", []):
            shared_state["current_step"] = step
            shared_state["critique"] = {}
            LOGGER.info("Current step: %s", self._step_description(step))

            for attempt in range(1, self.max_iterations_per_step + 1):
                shared_state["_attempt"] = attempt
                review_results: list[dict[str, Any]] = []

                for flow_index, agent_name in enumerate(step_flow, start=1):
                    if agent_name == "builder":
                        LOGGER.info("Agent running: Builder (attempt %s)", attempt)
                        shared_state["build"] = self.builder.run(shared_state)
                        LOGGER.info("Builder completed step output")
                        self._save_history(
                            state=shared_state,
                            agent_name="builder",
                            step=step,
                            attempt=attempt,
                            result=shared_state["build"],
                            flow_index=flow_index,
                        )
                    elif agent_name == "critic":
                        LOGGER.info(
                            "Agent running: Critic (review, attempt %s)",
                            attempt,
                        )
                        critique_result = self.critic.run(shared_state)
                        review_results.append(critique_result)
                        self._save_history(
                            state=shared_state,
                            agent_name="critic",
                            step=step,
                            attempt=attempt,
                            result=critique_result,
                            flow_index=flow_index,
                        )
                    elif agent_name == "research_critic":
                        shared_state["_critic_pass_label"] = "second_review"
                        LOGGER.info("Agent running: ResearchCritic (attempt %s)", attempt)
                        research_critique_result = self.research_critic.run(shared_state)
                        review_results.append(research_critique_result)
                        self._save_history(
                            state=shared_state,
                            agent_name="research_critic",
                            step=step,
                            attempt=attempt,
                            result=research_critique_result,
                            flow_index=flow_index,
                        )
                    else:
                        raise RuntimeError(f"Unsupported flow step: {agent_name}")

                shared_state["critique"] = self._merge_critic_results(review_results)
                LOGGER.info(
                    "Critic status: %s",
                    shared_state["critique"].get("status", "unknown"),
                )
                LOGGER.info(
                    "Critic issues: %s, fix instructions: %s",
                    len(shared_state["critique"].get("issues", [])),
                    len(shared_state["critique"].get("fix_instructions", [])),
                )

                if shared_state["critique"].get("status") == "pass":
                    break

        shared_state.pop("_attempt", None)
        shared_state.pop("_critic_pass_label", None)
        return shared_state

    def _ensure_required_keys(self, state: dict[str, Any], task: str) -> None:
        defaults = create_state(task)
        for key in REQUIRED_STATE_KEYS:
            state.setdefault(key, defaults[key])
        state["task"] = task

    def _save_history(
        self,
        state: dict[str, Any],
        agent_name: str,
        step: Any,
        attempt: int,
        result: dict[str, Any],
        flow_index: int | None = None,
    ) -> None:
        state["history"].append(
            {
                "agent": agent_name,
                "flow_index": flow_index,
                "step": step,
                "attempt": attempt,
                "result": deepcopy(result),
            }
        )

    def _step_description(self, step: Any) -> str:
        """Return a readable step description from a structured or plain step."""
        if isinstance(step, dict):
            return str(step.get("description", ""))
        return str(step)

    def _merge_critic_results(self, critic_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine one or more critic passes into a single feedback result."""
        issues: list[str] = []
        fix_instructions: list[str] = []

        for result in critic_results:
            issues.extend(result.get("issues", []))
            fix_instructions.extend(result.get("fix_instructions", []))

        status = "pass" if not issues else "revise"
        if status == "pass":
            issues = []
            fix_instructions = []

        return {
            "status": status,
            "issues": issues,
            "fix_instructions": fix_instructions,
        }
