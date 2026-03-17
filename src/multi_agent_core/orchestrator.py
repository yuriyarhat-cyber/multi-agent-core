"""Planner-builder-critic orchestration flow."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from .agents import (
    Analyzer,
    ArtifactTracker,
    Builder,
    CapabilityReport,
    Contrarian,
    Critic,
    Debugger,
    EscalationAgent,
    ExecutionPolicy,
    Planner,
    ResearchAgent,
    ResearchCritic,
    RecoveryPlanner,
    ResultSynthesizer,
    RunExporter,
    SessionMemory,
    SessionStrategist,
    Strategist,
    TaskBoard,
    Tester,
    ToolSelector,
    PriorityAgent,
)
from .router import Router
from .state import REQUIRED_STATE_KEYS, create_state


LOGGER = logging.getLogger(__name__)


class Orchestrator:
    """Run a small multi-agent workflow over shared state."""

    def __init__(
        self,
        router: Router | None = None,
        session_strategist: SessionStrategist | None = None,
        tool_selector: ToolSelector | None = None,
        session_memory: SessionMemory | None = None,
        task_board: TaskBoard | None = None,
        priority_agent: PriorityAgent | None = None,
        strategist: Strategist | None = None,
        planner: Planner | None = None,
        builder: Builder | None = None,
        artifact_tracker: ArtifactTracker | None = None,
        execution_policy: ExecutionPolicy | None = None,
        tester: Tester | None = None,
        critic: Critic | None = None,
        research_critic: ResearchCritic | None = None,
        contrarian: Contrarian | None = None,
        debugger: Debugger | None = None,
        analyzer: Analyzer | None = None,
        research_agent: ResearchAgent | None = None,
        result_synthesizer: ResultSynthesizer | None = None,
        capability_reporter: CapabilityReport | None = None,
        recovery_planner: RecoveryPlanner | None = None,
        escalation_agent: EscalationAgent | None = None,
        run_exporter: RunExporter | None = None,
        max_iterations_per_step: int = 3,
        autonomous_rounds: int = 2,
    ) -> None:
        self.router = router or Router()
        self.session_strategist = session_strategist or SessionStrategist()
        self.tool_selector = tool_selector or ToolSelector()
        self.session_memory = session_memory or SessionMemory()
        self.task_board = task_board or TaskBoard()
        self.priority_agent = priority_agent or PriorityAgent()
        self.strategist = strategist or Strategist()
        self.planner = planner or Planner()
        self.builder = builder or Builder()
        self.artifact_tracker = artifact_tracker or ArtifactTracker()
        self.execution_policy = execution_policy or ExecutionPolicy()
        self.tester = tester or Tester()
        self.critic = critic or Critic()
        self.research_critic = research_critic or ResearchCritic()
        self.contrarian = contrarian or Contrarian()
        self.debugger = debugger or Debugger()
        self.analyzer = analyzer or Analyzer()
        self.research_agent = research_agent or ResearchAgent()
        self.result_synthesizer = result_synthesizer or ResultSynthesizer()
        self.capability_reporter = capability_reporter or CapabilityReport()
        self.recovery_planner = recovery_planner or RecoveryPlanner()
        self.escalation_agent = escalation_agent or EscalationAgent()
        self.run_exporter = run_exporter or RunExporter()
        self.max_iterations_per_step = max(1, min(max_iterations_per_step, 3))
        self.autonomous_rounds = max(1, min(autonomous_rounds, 3))

    def run(self, task: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run the full routed multi-agent workflow for a task."""
        shared_state = create_state(task) if state is None else state
        self._ensure_required_keys(shared_state, task)
        shared_state["_max_rounds"] = self.autonomous_rounds
        shared_state["_memory_phase"] = "load"
        shared_state["memory"] = self.session_memory.run(shared_state)
        self._save_history(shared_state, "session_memory", None, 1, shared_state["memory"])
        for round_number in range(1, self.autonomous_rounds + 1):
            shared_state["current_round"] = round_number
            shared_state["task_board"] = self.task_board.run(shared_state)
            self._save_history(shared_state, "task_board", None, 1, shared_state["task_board"])
            shared_state["priorities"] = self.priority_agent.run(shared_state)
            self._save_history(shared_state, "priority_agent", None, 1, shared_state["priorities"])
            shared_state["session_strategy"] = self.session_strategist.run(shared_state)
            shared_state["subtasks"] = list(shared_state["session_strategy"].get("subtasks", shared_state["subtasks"]))
            shared_state["current_subtask"] = str(
                shared_state["session_strategy"].get("current_subtask", shared_state["current_subtask"])
            )
            shared_state["active_task"] = shared_state["current_subtask"] or shared_state["task"]
            self._save_history(shared_state, "session_strategist", None, 1, shared_state["session_strategy"])
            shared_state["task_board"] = self.task_board.run(shared_state)
            self._save_history(shared_state, "task_board", None, 1, shared_state["task_board"])
            shared_state["priorities"] = self.priority_agent.run(shared_state)
            self._save_history(shared_state, "priority_agent", None, 1, shared_state["priorities"])
            LOGGER.info("Starting autonomous round: %s", round_number)
            LOGGER.info("Current subtask: %s", shared_state["active_task"])
            self._run_single_round(shared_state)
            if (
                shared_state.get("current_subtask")
                and shared_state.get("critique", {}).get("status") == "pass"
                and shared_state["current_subtask"] not in shared_state["completed_subtasks"]
            ):
                shared_state["completed_subtasks"].append(shared_state["current_subtask"])
            shared_state["task_board"] = self.task_board.run(shared_state)
            self._save_history(shared_state, "task_board", None, 1, shared_state["task_board"])
            shared_state["priorities"] = self.priority_agent.run(shared_state)
            self._save_history(shared_state, "priority_agent", None, 1, shared_state["priorities"])
            shared_state["next_step"] = self._build_next_step(shared_state)
            self._save_history(shared_state, "next_step", None, 1, shared_state["next_step"])
            shared_state["session_strategy"] = self.session_strategist.run(shared_state)
            self._save_history(shared_state, "session_strategist", None, 1, shared_state["session_strategy"])
            shared_state["session_history"].append(
                {
                    "round": round_number,
                    "active_task": shared_state.get("active_task", ""),
                    "task_guidance": shared_state.get("task_guidance", ""),
                    "completed_subtasks": deepcopy(shared_state.get("completed_subtasks", [])),
                    "task_board": deepcopy(shared_state.get("task_board", {})),
                    "priorities": deepcopy(shared_state.get("priorities", {})),
                    "next_step": deepcopy(shared_state["next_step"]),
                    "session_strategy": deepcopy(shared_state["session_strategy"]),
                    "critique_status": shared_state.get("critique", {}).get("status", "unknown"),
                }
            )
            LOGGER.info("Recommended next step: %s", shared_state["next_step"].get("action", ""))
            if self._should_stop(shared_state, round_number):
                break
            shared_state["task_guidance"] = shared_state["session_strategy"].get("guidance", "")
            self._prepare_next_round(shared_state)

        shared_state["final_result"] = self.result_synthesizer.run(shared_state)
        self._save_history(shared_state, "result_synthesizer", None, 1, shared_state["final_result"])
        shared_state["capability_report"] = self.capability_reporter.run(shared_state)
        self._save_history(shared_state, "capability_report", None, 1, shared_state["capability_report"])
        shared_state["recovery_plan"] = self.recovery_planner.run(shared_state)
        self._save_history(shared_state, "recovery_planner", None, 1, shared_state["recovery_plan"])
        shared_state["escalation"] = self.escalation_agent.run(shared_state)
        self._save_history(shared_state, "escalation_agent", None, 1, shared_state["escalation"])
        shared_state["_memory_phase"] = "save"
        shared_state["memory"] = self.session_memory.run(shared_state)
        self._save_history(shared_state, "session_memory", None, 1, shared_state["memory"])
        shared_state["export"] = self.run_exporter.run(shared_state)
        self._save_history(shared_state, "run_exporter", None, 1, shared_state["export"])
        shared_state.pop("_attempt", None)
        shared_state.pop("_max_rounds", None)
        shared_state.pop("_memory_phase", None)
        return shared_state

    def _run_single_round(self, shared_state: dict[str, Any]) -> None:
        """Run one full routed flow pass."""
        shared_state["routing"] = self.router.route(shared_state["active_task"])
        LOGGER.info("Router task type: %s", shared_state["routing"].get("task_type"))
        LOGGER.info("Router reason: %s", shared_state["routing"].get("reason"))

        shared_state["tool_selection"] = self.tool_selector.run(shared_state)
        self._save_history(shared_state, "tool_selector", None, 1, shared_state["tool_selection"])
        LOGGER.info("Tool modes: %s", shared_state["tool_selection"].get("modes", {}))

        shared_state["strategy"] = self.strategist.run(shared_state)
        self._save_history(shared_state, "strategist", None, 1, shared_state["strategy"])

        shared_state["executed_flow"] = list(shared_state["strategy"].get("flow", []))
        LOGGER.info("Executing flow: %s", " -> ".join(shared_state["executed_flow"]))

        LOGGER.info("Agent running: Planner")
        shared_state["plan"] = self.planner.run(shared_state)
        self._save_history(shared_state, "planner", None, 1, shared_state["plan"])

        step_flow = [
            agent_name
            for agent_name in shared_state["executed_flow"]
            if agent_name not in {"strategist", "planner"}
        ]

        for step in shared_state["plan"].get("steps", []):
            shared_state["current_step"] = step
            shared_state["critique"] = {}
            shared_state["testing"] = {}
            shared_state["debugging"] = {}
            shared_state["analysis"] = {}
            shared_state["objections"] = {}
            shared_state["research"] = {}
            LOGGER.info("Current step: %s", self._step_description(step))

            for attempt in range(1, self.max_iterations_per_step + 1):
                shared_state["_attempt"] = attempt
                review_results: list[dict[str, Any]] = []

                for flow_index, agent_name in enumerate(step_flow, start=1):
                    if agent_name == "builder":
                        shared_state["policy"] = self.execution_policy.run(shared_state)
                        self._save_history(shared_state, "execution_policy", step, attempt, shared_state["policy"], flow_index)
                        if not shared_state["policy"].get("allowed", True):
                            shared_state["build"] = {
                                "step": self._step_description(step),
                                "content": "",
                                "used_feedback": False,
                                "applied_fix_instructions": [],
                            }
                            review_results.append(
                                {
                                    "status": "revise",
                                    "issues": [shared_state["policy"].get("reason", "Policy blocked the action.")],
                                    "fix_instructions": ["Choose a safer file path or reduce the number of file writes in this session."],
                                }
                            )
                            continue
                        LOGGER.info("Agent running: Builder (attempt %s)", attempt)
                        shared_state["build"] = self.builder.run(shared_state)
                        self._save_history(shared_state, "builder", step, attempt, shared_state["build"], flow_index)
                        shared_state["artifacts"] = self.artifact_tracker.run(shared_state)
                        self._save_history(shared_state, "artifact_tracker", step, attempt, shared_state["artifacts"], flow_index)
                    elif agent_name == "research_agent":
                        LOGGER.info("Agent running: ResearchAgent (attempt %s)", attempt)
                        shared_state["research"] = self.research_agent.run(shared_state)
                        self._save_history(shared_state, "research_agent", step, attempt, shared_state["research"], flow_index)
                    elif agent_name == "tester":
                        LOGGER.info("Agent running: Tester (attempt %s)", attempt)
                        shared_state["testing"] = self.tester.run(shared_state)
                        review_results.append(shared_state["testing"])
                        self._save_history(shared_state, "tester", step, attempt, shared_state["testing"], flow_index)
                    elif agent_name == "critic":
                        LOGGER.info("Agent running: Critic (attempt %s)", attempt)
                        critique_result = self.critic.run(shared_state)
                        review_results.append(critique_result)
                        self._save_history(shared_state, "critic", step, attempt, critique_result, flow_index)
                    elif agent_name == "research_critic":
                        LOGGER.info("Agent running: ResearchCritic (attempt %s)", attempt)
                        research_critique_result = self.research_critic.run(shared_state)
                        review_results.append(research_critique_result)
                        self._save_history(shared_state, "research_critic", step, attempt, research_critique_result, flow_index)
                    elif agent_name == "contrarian":
                        LOGGER.info("Agent running: Contrarian (attempt %s)", attempt)
                        shared_state["objections"] = self.contrarian.run(shared_state)
                        review_results.append(shared_state["objections"])
                        self._save_history(shared_state, "contrarian", step, attempt, shared_state["objections"], flow_index)
                    elif agent_name == "debugger":
                        shared_state["critique"] = self._merge_review_results(review_results)
                        LOGGER.info("Agent running: Debugger (attempt %s)", attempt)
                        shared_state["debugging"] = self.debugger.run(shared_state)
                        if shared_state["debugging"].get("status") == "active":
                            shared_state["critique"] = self._merge_review_results(review_results + [shared_state["debugging"]])
                        self._save_history(shared_state, "debugger", step, attempt, shared_state["debugging"], flow_index)
                    elif agent_name == "analyzer":
                        shared_state["critique"] = self._merge_review_results(
                            review_results + self._active_debug_result(shared_state)
                        )
                        LOGGER.info("Agent running: Analyzer (attempt %s)", attempt)
                        shared_state["analysis"] = self.analyzer.run(shared_state)
                        self._save_history(shared_state, "analyzer", step, attempt, shared_state["analysis"], flow_index)
                    else:
                        raise RuntimeError(f"Unsupported flow step: {agent_name}")

                shared_state["critique"] = self._merge_review_results(
                    review_results + self._active_debug_result(shared_state)
                )
                LOGGER.info("Review status: %s", shared_state["critique"].get("status", "unknown"))
                LOGGER.info(
                    "Review issues: %s, fix instructions: %s",
                    len(shared_state["critique"].get("issues", [])),
                    len(shared_state["critique"].get("fix_instructions", [])),
                )

                if shared_state["critique"].get("status") == "pass":
                    break

    def _ensure_required_keys(self, state: dict[str, Any], task: str) -> None:
        defaults = create_state(task)
        for key in REQUIRED_STATE_KEYS:
            state.setdefault(key, defaults[key])
        state["task"] = task
        state["active_task"] = state.get("active_task") or task

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

    def _merge_review_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine one or more review-style results into a single feedback result."""
        issues: list[str] = []
        fix_instructions: list[str] = []

        for result in results:
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

    def _active_debug_result(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Return debugger feedback only when it is active."""
        debugging = state.get("debugging") or {}
        if debugging.get("status") == "active":
            return [debugging]
        return []

    def _prepare_next_round(self, state: dict[str, Any]) -> None:
        """Reset round-specific fields while keeping full history."""
        state["routing"] = {}
        state["tool_selection"] = {}
        state["strategy"] = {}
        state["executed_flow"] = []
        state["plan"] = {"steps": [], "summary": ""}
        state["current_step"] = None
        state["build"] = {}
        state["artifacts"] = state.get("artifacts", {"items": []})
        state["policy"] = {}
        state["testing"] = {}
        state["critique"] = {}
        state["debugging"] = {}
        state["analysis"] = {}
        state["objections"] = {}
        state["research"] = {}
        state["session_strategy"] = {}
        state["active_task"] = state["task"]

    def _should_stop(self, state: dict[str, Any], round_number: int) -> bool:
        """Stop when the run is ready, out of rounds, or has no useful next move."""
        session_strategy = state.get("session_strategy") or {}
        critique = state.get("critique") or {}

        if round_number >= self.autonomous_rounds:
            return True
        if not session_strategy.get("continue_session"):
            return True
        if critique.get("status") != "revise":
            return True
        return False

    def _build_next_step(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a final agent-backed recommendation for what to do next."""
        analysis = state.get("analysis") or {}
        strategy = state.get("strategy") or {}
        objections = state.get("objections") or {}
        critique = state.get("critique") or {}

        return {
            "action": analysis.get("recommended_next_step", "Review the result and choose the next task."),
            "reason": analysis.get("reason") or strategy.get("reason", ""),
            "status": "needs_work" if critique.get("status") == "revise" else "ready",
            "confirmed_by": ["strategist", "analyzer", "session_strategist"],
            "watch_out_for": list(objections.get("objections", [])),
        }
