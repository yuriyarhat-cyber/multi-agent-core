"""Simple agent implementations used by the orchestrator."""

from __future__ import annotations

import logging
import json
import py_compile
import re
import subprocess
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .llm import codex_llm


LOGGER = logging.getLogger(__name__)


class _TextExtractor(HTMLParser):
    """Small HTML-to-text helper for research page fetching."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect visible text chunks from HTML."""
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        """Return normalized extracted text."""
        combined = " ".join(self._chunks)
        return re.sub(r"\s+", " ", unescape(combined)).strip()


def detect_file_action(task: str) -> tuple[str, str] | None:
    """Detect a simple file action and target path from task text."""
    patterns = [
        ("write_file", r"(?:create|write|создай|создать)\s+(?:a\s+)?(?:file\s+|файл\s+)([^\s,]+)"),
        ("append_file", r"(?:append|добавь)\s+(?:to\s+)?(?:file\s+|в\s+файл\s+|файл\s+)([^\s,]+)"),
        ("update_file", r"(?:update|modify|edit|измени|обнови)\s+(?:file\s+|файл\s+)([^\s,]+)"),
        ("read_file", r"(?:read|прочитай)\s+(?:file\s+|файл\s+)([^\s,]+)"),
    ]

    for action, pattern in patterns:
        match = re.search(pattern, task, flags=re.IGNORECASE)
        if match:
            return action, match.group(1).strip("\"'")
    return None


def extract_urls(text: str) -> list[str]:
    """Extract HTTP or HTTPS URLs from a piece of text."""
    return re.findall(r"https?://[^\s)>\]]+", text, flags=re.IGNORECASE)


def get_active_task(state: dict[str, Any]) -> str:
    """Return the active subtask when present, otherwise the top-level task."""
    return str(state.get("active_task") or state.get("current_subtask") or state.get("task", "")).strip()


def decompose_task(task: str) -> list[str]:
    """Split a larger task into a few smaller subtasks using simple separators."""
    normalized = re.sub(r"\s+", " ", task).strip()
    if extract_urls(normalized):
        return [normalized] if normalized else []
    parts = re.split(r"\bthen\b|\band\b|,|;| затем | потом ", normalized, flags=re.IGNORECASE)
    cleaned = [part.strip(" .") for part in parts if part.strip(" .")]
    if len(cleaned) <= 1:
        return [normalized] if normalized else []
    unique_parts: list[str] = []
    for part in cleaned:
        if part not in unique_parts:
            unique_parts.append(part)
    return unique_parts[:3]


def get_memory_note(state: dict[str, Any]) -> str:
    """Return a short note from previous session memory when available."""
    memory = state.get("memory") or {}
    latest_summary = str(memory.get("latest_summary", "")).strip()
    if not latest_summary:
        return ""
    return f" Previous session summary: {latest_summary}."


class Agent:
    """Base class for all agents."""

    name = "agent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Read the shared state and return this agent's structured result."""
        raise NotImplementedError("Agent subclasses must implement run().")


class ArtifactTracker(Agent):
    """Track created or updated artifacts across rounds and subtasks."""

    name = "artifact_tracker"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Record the latest build result as a reusable artifact when relevant."""
        build = state.get("build") or {}
        active_task = get_active_task(state)
        existing_items = list((state.get("artifacts") or {}).get("items", []))
        path = str(build.get("path", "")).strip()
        content = str(build.get("content", "")).strip()
        artifact_type = "file" if path else "result"

        if not path and not content:
            return {"items": existing_items, "latest": None}

        latest = {
            "task": active_task,
            "type": artifact_type,
            "path": path,
            "action": str(build.get("action", "")).strip(),
            "content_preview": content[:160],
        }

        deduped_items = [item for item in existing_items if not (path and item.get("path") == path)]
        if latest not in deduped_items:
            deduped_items.append(latest)

        return {
            "items": deduped_items,
            "latest": latest,
        }


class ExecutionPolicy(Agent):
    """Apply small safety checks before file-writing actions happen."""

    name = "execution_policy"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return whether the current action is allowed and why."""
        task = get_active_task(state)
        file_action = detect_file_action(task)
        project_root = Path(state.get("project_root") or Path.cwd()).resolve()
        artifacts = list((state.get("artifacts") or {}).get("items", []))
        created_files = [item for item in artifacts if item.get("path")]
        max_files_per_session = 5

        if file_action is None:
            return {
                "allowed": True,
                "reason": "No file action detected for this task.",
                "checked_path": "",
            }

        action, relative_path = file_action
        target_path = (project_root / relative_path).resolve()

        if not str(target_path).startswith(str(project_root)):
            return {
                "allowed": False,
                "reason": "File actions must stay inside project_root.",
                "checked_path": str(target_path),
            }

        if action in {"write_file", "append_file", "update_file"} and len(created_files) >= max_files_per_session:
            return {
                "allowed": False,
                "reason": "This session already created many files. Stop and review the artifacts before continuing.",
                "checked_path": str(target_path),
            }

        return {
            "allowed": True,
            "reason": "The file action is inside project_root and within the session limits.",
            "checked_path": str(target_path),
        }


class ToolSelector(Agent):
    """Choose which simple tool modes are useful for the current task."""

    name = "tool_selector"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return tool mode flags for the current active task."""
        active_task = get_active_task(state).lower()
        routing = state.get("routing") or {}
        task_type = str(routing.get("task_type", "general_task"))
        file_action = detect_file_action(active_task)
        has_urls = bool(extract_urls(active_task))

        modes = {
            "file_mode": bool(file_action),
            "test_mode": bool(file_action and str(file_action[1]).lower().endswith(".py")),
            "research_mode": task_type == "research_task" and has_urls,
            "synthesis_mode": True,
        }

        reasons = []
        if modes["file_mode"]:
            reasons.append("The task includes a file action.")
        if modes["test_mode"]:
            reasons.append("The target looks like a Python file, so tests may help.")
        if modes["research_mode"]:
            reasons.append("The task is a research task with URL sources.")
        if modes["synthesis_mode"]:
            reasons.append("The session should always produce a final synthesized result.")

        return {
            "task_type": task_type,
            "modes": modes,
            "reason": " ".join(reasons),
        }


class ResultSynthesizer(Agent):
    """Build a final human-readable summary from the completed session state."""

    name = "result_synthesizer"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a concise final summary of what happened in the session."""
        critique = state.get("critique") or {}
        artifacts = list((state.get("artifacts") or {}).get("items", []))
        completed_subtasks = list(state.get("completed_subtasks", []))
        current_subtask = str(state.get("current_subtask", "")).strip()
        next_step = state.get("next_step") or {}
        build = state.get("build") or {}
        status = "ready" if critique.get("status") == "pass" else "needs_work"

        created_files = [item["path"] for item in artifacts if item.get("path")]
        if completed_subtasks:
            completed_text = ", ".join(completed_subtasks)
        elif current_subtask:
            completed_text = current_subtask
        else:
            completed_text = state.get("task", "")

        summary_parts = [
            f"Session status: {status}.",
            f"Completed work: {completed_text}.",
        ]
        if created_files:
            summary_parts.append(f"Artifacts: {', '.join(created_files)}.")
        elif build.get("content"):
            summary_parts.append("A draft result was produced.")

        attention = list(critique.get("issues", []))
        if not attention and next_step.get("status") == "needs_work":
            attention.append(str(next_step.get("action", "")).strip())

        return {
            "status": status,
            "summary": " ".join(part for part in summary_parts if part),
            "completed_subtasks": completed_subtasks,
            "artifacts": created_files,
            "needs_attention": attention,
            "next_recommendation": str(next_step.get("action", "")).strip(),
        }


class CapabilityReport(Agent):
    """Summarize which capabilities were available and actually used."""

    name = "capability_report"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a compact capability usage report for the finished session."""
        tool_selection = state.get("tool_selection") or {}
        modes = tool_selection.get("modes") or {}
        history = list(state.get("history", []))
        used_agents = {entry.get("agent", "") for entry in history}
        artifacts = list((state.get("artifacts") or {}).get("items", []))
        research = state.get("research") or {}
        testing = state.get("testing") or {}

        available = [
            name for name, enabled in modes.items() if enabled
        ]
        used = []
        if "builder" in used_agents:
            used.append("build")
        if "artifact_tracker" in used_agents or artifacts:
            used.append("artifact_tracking")
        if "tester" in used_agents or testing.get("checks"):
            used.append("testing")
        if "research_agent" in used_agents or research.get("findings"):
            used.append("research")
        if "result_synthesizer" in used_agents:
            used.append("final_synthesis")
        if "execution_policy" in used_agents:
            used.append("policy")

        available_set = set(available)
        used_mode_aliases = {
            "file_mode": "build",
            "test_mode": "testing",
            "research_mode": "research",
            "synthesis_mode": "final_synthesis",
        }
        unused = [
            mode_name
            for mode_name, alias in used_mode_aliases.items()
            if mode_name in available_set and alias not in used
        ]

        return {
            "available_modes": available,
            "used_capabilities": used,
            "unused_available_modes": unused,
            "used_agents": sorted(agent for agent in used_agents if agent),
        }


class RunExporter(Agent):
    """Optionally export the finished session result to a JSON file."""

    name = "run_exporter"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Write a compact run report to disk when export is enabled."""
        export_enabled = bool(state.get("export_enabled"))
        if not export_enabled:
            return {
                "enabled": False,
                "written": False,
                "path": "",
                "reason": "Export is disabled for this run.",
            }

        project_root = Path(state.get("project_root") or Path.cwd()).resolve()
        export_dir = project_root / "runs"
        export_dir.mkdir(parents=True, exist_ok=True)
        round_number = int(state.get("current_round", 1))
        export_path = export_dir / f"run_report_round_{round_number}.json"

        payload = {
            "task": state.get("task", ""),
            "active_task": state.get("active_task", ""),
            "final_result": state.get("final_result", {}),
            "capability_report": state.get("capability_report", {}),
            "next_step": state.get("next_step", {}),
            "completed_subtasks": state.get("completed_subtasks", []),
            "artifacts": state.get("artifacts", {}),
        }
        export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        return {
            "enabled": True,
            "written": True,
            "path": str(export_path),
            "reason": "Run report exported successfully.",
        }


class SessionMemory(Agent):
    """Load and save a small cross-run memory file inside the project."""

    name = "session_memory"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Load or save session memory depending on the requested phase."""
        phase = str(state.get("_memory_phase", "load"))
        project_root = Path(state.get("project_root") or Path.cwd()).resolve()
        memory_path = project_root / ".multi_agent_core_memory.json"

        if phase == "load":
            return self._load(memory_path)
        if phase == "save":
            return self._save(memory_path, state)
        raise RuntimeError(f"Unsupported memory phase: {phase}")

    def _load(self, memory_path: Path) -> dict[str, Any]:
        """Load memory from disk when available."""
        if not memory_path.exists():
            return {
                "enabled": True,
                "path": str(memory_path),
                "entries": [],
                "latest_summary": "",
                "status": "empty",
            }

        try:
            data = json.loads(memory_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {
                "enabled": True,
                "path": str(memory_path),
                "entries": [],
                "latest_summary": "",
                "status": "invalid",
            }

        entries = list(data.get("entries", []))
        latest_summary = str(entries[-1].get("summary", "")) if entries else ""
        return {
            "enabled": True,
            "path": str(memory_path),
            "entries": entries,
            "latest_summary": latest_summary,
            "status": "loaded",
        }

    def _save(self, memory_path: Path, state: dict[str, Any]) -> dict[str, Any]:
        """Save a compact memory entry for this run."""
        existing = self._load(memory_path)
        entries = list(existing.get("entries", []))
        final_result = state.get("final_result") or {}
        capability_report = state.get("capability_report") or {}
        next_step = state.get("next_step") or {}

        entry = {
            "task": state.get("task", ""),
            "summary": final_result.get("summary", ""),
            "status": final_result.get("status", ""),
            "artifacts": list(final_result.get("artifacts", [])),
            "used_capabilities": list(capability_report.get("used_capabilities", [])),
            "next_recommendation": next_step.get("action", ""),
        }
        entries.append(entry)
        entries = entries[-20:]

        payload = {"entries": entries}
        memory_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

        return {
            "enabled": True,
            "path": str(memory_path),
            "entries": entries,
            "latest_summary": entry["summary"],
            "status": "saved",
        }


class RecoveryPlanner(Agent):
    """Build a small recovery plan when the session ends in needs_work state."""

    name = "recovery_planner"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a structured fallback plan for recovering from a stuck session."""
        final_result = state.get("final_result") or {}
        critique = state.get("critique") or {}
        testing = state.get("testing") or {}
        policy = state.get("policy") or {}
        debugging = state.get("debugging") or {}

        if final_result.get("status") != "needs_work":
            return {
                "status": "not_needed",
                "reason": "The session finished in a ready state.",
                "steps": [],
            }

        steps: list[str] = []
        issues = list(critique.get("issues", []))
        if not policy.get("allowed", True):
            steps.append(f"Resolve the policy issue first: {policy.get('reason', '')}".strip())
        if testing.get("stderr") or testing.get("stdout"):
            steps.append("Review the latest unittest output and fix the failing code path.")
        if debugging.get("debug_notes"):
            steps.append("Use the debugger notes to target the next correction.")
        if issues:
            steps.append(f"Address the top critique issue: {issues[0]}")
        steps.append("Retry the task with a narrower scope or a clearer instruction.")

        deduped_steps: list[str] = []
        for step in steps:
            cleaned = step.strip()
            if cleaned and cleaned not in deduped_steps:
                deduped_steps.append(cleaned)

        return {
            "status": "needed",
            "reason": "The session still needs work after its autonomous rounds.",
            "steps": deduped_steps,
        }


class TaskBoard(Agent):
    """Maintain simple queued/active/done/blocked status for subtasks."""

    name = "task_board"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Update the task board from current subtasks and session status."""
        subtasks = list(state.get("subtasks", []))
        current_subtask = str(state.get("current_subtask", "")).strip()
        completed_subtasks = set(state.get("completed_subtasks", []))
        critique = state.get("critique") or {}
        existing = list((state.get("task_board") or {}).get("items", []))
        existing_map = {str(item.get("task", "")): item for item in existing}
        items: list[dict[str, str]] = []

        for subtask in subtasks:
            previous = dict(existing_map.get(subtask, {}))
            status = "queued"
            if subtask in completed_subtasks:
                status = "done"
            elif subtask == current_subtask:
                status = "blocked" if critique.get("status") == "revise" else "active"

            items.append(
                {
                    "task": subtask,
                    "status": status,
                    "note": previous.get("note", ""),
                }
            )

        summary = {
            "queued": sum(1 for item in items if item["status"] == "queued"),
            "active": sum(1 for item in items if item["status"] == "active"),
            "done": sum(1 for item in items if item["status"] == "done"),
            "blocked": sum(1 for item in items if item["status"] == "blocked"),
        }

        return {
            "items": items,
            "summary": summary,
        }


class EscalationAgent(Agent):
    """Decide when the autonomous session should stop and ask for human help."""

    name = "escalation_agent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return an escalation decision with a clear reason."""
        final_result = state.get("final_result") or {}
        recovery_plan = state.get("recovery_plan") or {}
        policy = state.get("policy") or {}
        session_history = list(state.get("session_history", []))
        critique = state.get("critique") or {}

        if final_result.get("status") == "ready":
            return {
                "needed": False,
                "reason": "The session finished in a ready state.",
                "recommendation": "",
            }

        revise_rounds = sum(1 for item in session_history if item.get("critique_status") == "revise")
        blocked_rounds = 0
        for item in session_history:
            board = item.get("task_board", {}) if isinstance(item, dict) else {}
            summary = board.get("summary", {}) if isinstance(board, dict) else {}
            blocked_rounds += int(summary.get("blocked", 0) or 0)

        if not policy.get("allowed", True):
            return {
                "needed": True,
                "reason": f"Autonomous work is blocked by policy: {policy.get('reason', '')}".strip(),
                "recommendation": "A human should confirm a safer path or change the task scope.",
            }

        if revise_rounds >= 2 and recovery_plan.get("status") == "needed":
            return {
                "needed": True,
                "reason": "The session stayed in needs_work across multiple rounds and already produced a recovery plan.",
                "recommendation": "A human should review the recovery plan and decide the next intervention.",
            }

        if blocked_rounds >= 2:
            return {
                "needed": True,
                "reason": "The task board stayed blocked across the session.",
                "recommendation": "A human should unblock the current subtask or change priorities.",
            }

        if critique.get("status") == "revise" and not recovery_plan.get("steps"):
            return {
                "needed": True,
                "reason": "The session still needs work but did not find a clear autonomous recovery path.",
                "recommendation": "A human should refine the task or provide a narrower instruction.",
            }

        return {
            "needed": False,
            "reason": "The session can stop without escalation.",
            "recommendation": "",
        }


class PriorityAgent(Agent):
    """Assign simple priorities to subtasks so the session can choose the next one better."""

    name = "priority_agent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return priority scores and suggested order for current board items."""
        board = state.get("task_board") or {}
        critique = state.get("critique") or {}
        items = list(board.get("items", []))
        scored: list[dict[str, Any]] = []

        for item in items:
            task = str(item.get("task", ""))
            status = str(item.get("status", "queued"))
            score = 10
            reason_parts: list[str] = []

            if status == "blocked":
                score = 100
                reason_parts.append("Blocked tasks need attention first.")
            elif status == "active":
                score = 80
                reason_parts.append("The active task should usually continue.")
            elif status == "queued":
                score = 50
                reason_parts.append("Queued work is available for the next round.")
            elif status == "done":
                score = 0
                reason_parts.append("Completed work stays at the bottom.")

            if detect_file_action(task):
                score += 5
                reason_parts.append("File tasks often produce concrete progress.")
            if extract_urls(task):
                score += 3
                reason_parts.append("Research tasks with URLs can use live evidence.")
            if critique.get("status") == "revise" and status == "blocked":
                score += 10
                reason_parts.append("Current critique still requests revision.")

            scored.append(
                {
                    "task": task,
                    "status": status,
                    "priority": score,
                    "reason": " ".join(reason_parts),
                }
            )

        ordered = sorted(scored, key=lambda item: (-int(item["priority"]), item["task"]))
        return {
            "items": ordered,
            "next_task": ordered[0]["task"] if ordered else "",
        }


class Strategist(Agent):
    """Choose a practical orchestration flow for the current task."""

    name = "strategist"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a recommended flow and a short explanation."""
        routing = state.get("routing") or {}
        tool_selection = state.get("tool_selection") or {}
        task_type = str(routing.get("task_type", "general_task"))
        has_research_urls = bool(state.get("research_urls") or extract_urls(str(state.get("task", ""))))
        task_guidance = str(state.get("task_guidance", "")).strip()

        if task_type == "file_task":
            flow = ["strategist", "planner", "builder", "tester", "critic", "contrarian", "debugger", "analyzer"]
            reason = "File tasks benefit from building, testing, challenge, and debugging."
        elif task_type == "text_task":
            flow = ["strategist", "planner", "builder", "critic", "contrarian", "debugger", "analyzer"]
            reason = "Text tasks benefit from drafting, critique, and challenge."
        elif task_type == "research_task":
            flow = ["strategist", "planner", "builder", "critic", "research_critic", "contrarian", "debugger", "analyzer"]
            if has_research_urls:
                flow.insert(3, "research_agent")
                reason = "Research tasks use live URL fetching and deeper review."
            else:
                reason = "Research tasks use deeper review. Add URL(s) to enable live research fetching."
        else:
            flow = ["strategist", "planner", "builder", "critic", "debugger", "analyzer"]
            reason = "General tasks use a lightweight build-review-debug flow."

        tool_note = ""
        if tool_selection.get("modes"):
            active_modes = [name for name, enabled in tool_selection["modes"].items() if enabled]
            if active_modes:
                tool_note = f" Active modes: {', '.join(active_modes)}."

        return {
            "task_type": task_type,
            "flow": flow,
            "reason": f"{reason}{tool_note} Guidance: {task_guidance}" if task_guidance else f"{reason}{tool_note}",
        }


class SessionStrategist(Agent):
    """Decide whether the orchestrator should continue into another round."""

    name = "session_strategist"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return session-level guidance for the next autonomous round."""
        task = str(state.get("task", "")).strip()
        memory_note = get_memory_note(state)
        critique = state.get("critique") or {}
        next_step = state.get("next_step") or {}
        current_round = int(state.get("current_round", 1))
        max_rounds = int(state.get("_max_rounds", 1))
        action = str(next_step.get("action", "")).strip()
        status = str(next_step.get("status", "ready"))
        subtasks = list(state.get("subtasks") or decompose_task(task))
        if not subtasks:
            fallback_task = task or "current task"
            subtasks = [fallback_task]
        completed_subtasks = list(state.get("completed_subtasks", []))
        remaining_subtasks = [subtask for subtask in subtasks if subtask not in completed_subtasks]
        priorities = state.get("priorities") or {}
        priority_items = list(priorities.get("items", []))
        prioritized_next = str(priorities.get("next_task", "")).strip()
        current_subtask = str(
            state.get("current_subtask")
            or prioritized_next
            or (remaining_subtasks[0] if remaining_subtasks else task)
        )

        if not next_step:
            return {
                "continue_session": True,
                "guidance": str(state.get("task_guidance", "")).strip(),
                "reason": "Starting autonomous session planning.",
                "confirmed_next_step": "",
                "subtasks": subtasks,
                "current_subtask": current_subtask,
            }

        if not remaining_subtasks:
            continue_session = False
            guidance = ""
            reason = f"All identified subtasks are complete.{memory_note}"
            current_subtask = ""
        elif current_round >= max_rounds:
            continue_session = False
            guidance = ""
            reason = f"The autonomous round limit has been reached.{memory_note}"
        elif critique.get("status") == "pass" and len(remaining_subtasks) > 1:
            continue_session = True
            guidance = ""
            if prioritized_next and prioritized_next in remaining_subtasks:
                current_subtask = prioritized_next
            else:
                current_subtask = remaining_subtasks[1]
            reason = f"The current subtask is complete, so the session can move to the next subtask.{memory_note}"
        elif status == "needs_work" and action:
            continue_session = True
            guidance = action
            reason = f"Another round is useful because the agents still see concrete follow-up work.{memory_note}"
        elif critique.get("status") == "revise":
            continue_session = True
            guidance = action or "Apply the latest review feedback."
            reason = f"The latest critique still requests revision.{memory_note}"
        else:
            continue_session = False
            guidance = ""
            reason = f"The result is ready enough to stop the autonomous session.{memory_note}"

        return {
            "continue_session": continue_session,
            "guidance": guidance,
            "reason": reason,
            "confirmed_next_step": action,
            "subtasks": subtasks,
            "current_subtask": current_subtask,
        }


class Planner(Agent):
    """Break a task into a small list of reusable steps."""

    name = "planner"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a stable structured plan for file, text, research, or general tasks."""
        task = get_active_task(state)
        task_guidance = str(state.get("task_guidance", "")).strip()
        tool_selection = state.get("tool_selection") or {}
        memory_note = get_memory_note(state)
        guidance_note = f" Follow this guidance: {task_guidance}." if task_guidance else ""
        tool_note = self._format_tool_note(tool_selection)
        summary = codex_llm(f"Plan task: {task}.{tool_note}{memory_note}{guidance_note}")
        routing = state.get("routing") or {}
        strategy = state.get("strategy") or {}
        task_type = routing.get("task_type", "general_task")
        file_action = detect_file_action(task)

        if task_type == "file_task":
            if file_action is not None:
                action, target_file = file_action
            else:
                action, target_file = "write_file", "target file"
            plan = {
                "type": "file_task",
                "summary": summary,
                "target_file": target_file,
                "file_action": action,
                "steps": [
                    {"id": "identify_target_file", "kind": "analysis", "description": f"Determine the target file: {target_file}"},
                    {"id": "confirm_file_action", "kind": "analysis", "description": f"Confirm the file action: {action}"},
                    {"id": "prepare_file_content", "kind": "build", "description": f"Prepare the content for {target_file}"},
                    {"id": "save_file_changes", "kind": "write", "description": f"Save the changes to {target_file}"},
                    {"id": "verify_file_result", "kind": "review", "description": f"Check the final result in {target_file}"},
                ],
            }
        elif task_type == "text_task":
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the text task"
            plan = {
                "type": "text_task",
                "summary": summary,
                "steps": [
                    {"id": "understand_text_goal", "kind": "analysis", "description": f"Understand the text goal: {focus}"},
                    {"id": "draft_text", "kind": "build", "description": f"Draft the text for: {focus}"},
                    {"id": "review_text", "kind": "review", "description": f"Review and tighten the text for: {focus}"},
                ],
            }
        elif task_type == "research_task":
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the research task"
            plan = {
                "type": "research_task",
                "summary": summary,
                "strategy_reason": strategy.get("reason", ""),
                "steps": [
                    {"id": "define_research_goal", "kind": "analysis", "description": f"Define what to analyze for: {focus}"},
                    {"id": "compare_findings", "kind": "analysis", "description": f"Compare the key points for: {focus}"},
                    {"id": "summarize_conclusion", "kind": "review", "description": f"Summarize the conclusion for: {focus}"},
                    {"id": "prepare_deeper_review", "kind": "review", "description": f"Prepare for deeper review and challenge of: {focus}"},
                ],
            }
        else:
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the task"
            plan = {
                "type": "general_task",
                "summary": summary,
                "steps": [
                    {"id": "understand_goal", "kind": "analysis", "description": f"Understand the goal: {focus}"},
                    {"id": "prepare_output", "kind": "build", "description": f"Prepare a first result for: {focus}"},
                    {"id": "review_result", "kind": "review", "description": f"Review the result for: {focus}"},
                ],
            }

        LOGGER.info("Planner selected plan type: %s", plan["type"])
        LOGGER.info("Planner created %s step(s)", len(plan["steps"]))
        return plan

    def _format_tool_note(self, tool_selection: dict[str, Any]) -> str:
        """Format selected tool modes into planner guidance."""
        modes = tool_selection.get("modes") or {}
        enabled = [name for name, active in modes.items() if active]
        if not enabled:
            return ""
        return f" Use these modes: {', '.join(enabled)}."


class Builder(Agent):
    """Produce output for the current step."""

    name = "builder"

    def read_file(self, path: str) -> str:
        """Read a UTF-8 text file from the project."""
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        """Write a UTF-8 text file, creating parent folders when needed."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    def append_file(self, path: str, content: str) -> None:
        """Append UTF-8 text to a file, creating parent folders when needed."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(content)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a draft output for the current step, using feedback if present."""
        step = state.get("current_step") or ""
        task = get_active_task(state)
        task_guidance = str(state.get("task_guidance", "")).strip()
        previous_critique = state.get("critique") or {}
        research = state.get("research") or {}
        artifacts = state.get("artifacts") or {}
        tool_selection = state.get("tool_selection") or {}
        memory_note = get_memory_note(state)
        issues = previous_critique.get("issues") or []
        fix_instructions = previous_critique.get("fix_instructions") or []
        project_root = Path(state.get("project_root") or Path.cwd())
        feedback_note = ""
        if fix_instructions:
            feedback_note = f" Apply these fixes: {'; '.join(fix_instructions)}."
        elif issues:
            feedback_note = f" Revised to address: {'; '.join(issues)}."
        research_note = self._format_research_note(research)
        artifact_note = self._format_artifact_note(artifacts)
        tool_note = self._format_tool_note(tool_selection)
        guidance_note = f" Follow this task guidance: {task_guidance}." if task_guidance else ""

        file_action = detect_file_action(str(task))
        if file_action is not None:
            action, relative_path = file_action
            target_path = project_root / relative_path
            return self._run_file_action(
                action=action,
                target_path=target_path,
                task=str(task),
                step=self._step_description(step),
                feedback_note=feedback_note,
                guidance_note=guidance_note,
                artifact_note=artifact_note,
                research_note=research_note,
                tool_note=tool_note,
                memory_note=memory_note,
                fix_instructions=list(fix_instructions),
            )

        step_description = self._step_description(step)
        prompt = (
            f"Build step '{step_description}' for task '{task}'."
            f"{tool_note}{memory_note}{guidance_note}{artifact_note}{research_note}{feedback_note}"
        )
        content = (
            f"Step: {step_description}\n"
            f"Task: {task}\n"
            f"Draft: {codex_llm(prompt)}.{tool_note}{memory_note}{guidance_note}{artifact_note}{research_note}{feedback_note}"
        ).strip()

        return {
            "step": step_description,
            "content": content,
            "used_feedback": bool(issues or fix_instructions),
            "applied_fix_instructions": list(fix_instructions),
        }

    def _format_research_note(self, research: dict[str, Any]) -> str:
        """Format research findings into a short builder prompt suffix."""
        findings = research.get("findings") or []
        if not findings:
            return ""

        bullets = []
        for finding in findings[:3]:
            source = finding.get("url", "unknown source")
            excerpt = str(finding.get("excerpt", "")).strip()
            if excerpt:
                bullets.append(f"{source}: {excerpt}")

        if not bullets:
            return ""
        return f" Use these research notes: {' | '.join(bullets)}."

    def _format_artifact_note(self, artifacts: dict[str, Any]) -> str:
        """Format previously created artifacts into a short builder prompt suffix."""
        items = list(artifacts.get("items", []))
        if not items:
            return ""

        notes = []
        for item in items[-3:]:
            path = str(item.get("path", "")).strip()
            preview = str(item.get("content_preview", "")).strip()
            if path:
                notes.append(f"{path}: {preview}")
            elif preview:
                notes.append(preview)

        if not notes:
            return ""
        return f" Reuse these earlier artifacts when helpful: {' | '.join(notes)}."

    def _format_tool_note(self, tool_selection: dict[str, Any]) -> str:
        """Format selected tool modes into builder guidance."""
        modes = tool_selection.get("modes") or {}
        enabled = [name for name, active in modes.items() if active]
        if not enabled:
            return ""
        return f" Use these modes: {', '.join(enabled)}."

    def _step_description(self, step: Any) -> str:
        """Return a readable step description from a structured or plain step."""
        if isinstance(step, dict):
            return str(step.get("description", ""))
        return str(step)

    def _run_file_action(
        self,
        action: str,
        target_path: Path,
        task: str,
        step: str,
        feedback_note: str,
        guidance_note: str,
        artifact_note: str,
        research_note: str,
        tool_note: str,
        memory_note: str,
        fix_instructions: list[str],
    ) -> dict[str, Any]:
        """Perform a simple file action and return structured build output."""
        target_path = target_path.resolve()
        existing_content = ""

        if action in {"update_file", "append_file", "read_file"} and target_path.exists():
            LOGGER.info("Reading file: %s", target_path)
            existing_content = self.read_file(str(target_path))

        if action == "read_file":
            return {
                "step": step,
                "action": action,
                "path": str(target_path),
                "content": existing_content,
                "used_feedback": bool(feedback_note),
                "applied_fix_instructions": list(fix_instructions),
            }

        prompt = (
            f"Task: {task}\n"
            f"Step: {step}\n"
            f"Target file: {target_path.name}\n"
            f"Existing content:\n{existing_content}\n"
            f"Produce only the file content.{tool_note}{memory_note}{guidance_note}{artifact_note}{research_note}{feedback_note}"
        )
        generated_content = codex_llm(prompt)

        if action == "append_file":
            LOGGER.info("Appending file: %s", target_path)
            text_to_append = generated_content if generated_content.endswith("\n") else generated_content + "\n"
            self.append_file(str(target_path), text_to_append)
            final_content = self.read_file(str(target_path))
        else:
            LOGGER.info("Writing file: %s", target_path)
            self.write_file(str(target_path), generated_content)
            final_content = generated_content

        return {
            "step": step,
            "action": "write_file" if action == "update_file" else action,
            "path": str(target_path),
            "content": final_content,
            "used_feedback": bool(feedback_note),
            "applied_fix_instructions": list(fix_instructions),
        }


class Tester(Agent):
    """Run lightweight checks against the builder result."""

    name = "tester"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return test status plus any concrete fixes."""
        build = state.get("build") or {}
        task = get_active_task(state)
        path = build.get("path")
        content = str(build.get("content", "")).strip()
        project_root = Path(state.get("project_root") or Path.cwd())
        issues: list[str] = []
        fix_instructions: list[str] = []
        checks: list[str] = []
        command: list[str] = []
        stdout = ""
        stderr = ""

        if not content:
            issues.append("Builder result is empty")
            fix_instructions.append("Produce a non-empty result before testing.")

        if path:
            file_path = Path(str(path))
            checks.append(f"checked path {file_path}")
            if not file_path.exists():
                issues.append("Expected output file was not created")
                fix_instructions.append("Create the target file before finishing the step.")
            elif file_path.suffix == ".py":
                try:
                    py_compile.compile(str(file_path), doraise=True)
                    checks.append("python syntax check passed")
                except py_compile.PyCompileError as exc:
                    issues.append("Python file has a syntax error")
                    fix_instructions.append(f"Fix the Python syntax error: {exc.msg}")

        if self._should_run_project_tests(task, build, project_root):
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
            LOGGER.info("Tester running project tests: %s", " ".join(command))
            checks.append("ran project unittest suite")
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except OSError as exc:
                issues.append("Could not run the project test suite")
                fix_instructions.append("Make sure the project tests can be started from the project root.")
                stderr = str(exc)
            else:
                stdout = completed.stdout.strip()
                stderr = completed.stderr.strip()
                if completed.returncode != 0:
                    issues.append("Project tests failed")
                    fix_instructions.append("Read the failing unittest output and fix the code or tests that are breaking.")

        status = "pass" if not issues else "revise"
        if status == "pass":
            issues = []
            fix_instructions = []

        return {
            "status": status,
            "issues": issues,
            "fix_instructions": fix_instructions,
            "checks": checks,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
        }

    def _should_run_project_tests(self, task: str, build: dict[str, Any], project_root: Path) -> bool:
        """Decide whether it is worth running the local unittest suite."""
        path = str(build.get("path", "")).lower()
        action = str(build.get("action", "")).lower()
        task_lower = task.lower()
        tests_dir = project_root / "tests"

        if not tests_dir.exists():
            return False
        if path.endswith(".py"):
            return True
        if action in {"write_file", "update_file", "append_file"} and path:
            return True
        return any(keyword in task_lower for keyword in ["test", "tests", "python", "module", "script", "file"])


class Critic(Agent):
    """Check the builder output and decide whether it passes."""

    name = "critic"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return pass or revise, plus a list of issues to fix."""
        build = state.get("build") or {}
        content = str(build.get("content", "")).strip()
        attempt = int(state.get("_attempt", 1))
        issues: list[str] = []
        fix_instructions: list[str] = []

        if not content:
            issues.append("Builder returned empty content")
            fix_instructions.append("Generate non-empty output for the current step.")

        if attempt == 1 and "Apply these fixes:" not in content and "Revised to address:" not in content:
            issues.append("Add a revision note to show the feedback loop")
            fix_instructions.append("Add a short revision note that clearly reflects the critic feedback.")

        status = "pass" if not issues else "revise"
        if status == "pass":
            issues = []
            fix_instructions = []

        LOGGER.info("Critic status: %s", status)
        LOGGER.info("Critic found %s issue(s)", len(issues))
        LOGGER.info("Critic prepared %s fix instruction(s)", len(fix_instructions))
        return {
            "status": status,
            "issues": issues,
            "fix_instructions": fix_instructions,
        }


class ResearchCritic(Agent):
    """Perform a deeper review for research-style tasks."""

    name = "research_critic"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return pass or revise, plus deeper research-specific guidance."""
        task = get_active_task(state).lower()
        build = state.get("build") or {}
        content = str(build.get("content", "")).strip()
        issues: list[str] = []
        fix_instructions: list[str] = []

        if not content:
            issues.append("Research result is empty")
            fix_instructions.append("Add a complete research answer before final review.")

        if len(content.split()) < 12:
            issues.append("Research result is too brief")
            fix_instructions.append("Expand the answer so it is less superficial and covers the main points.")

        if "compare" in task and "compare" not in content.lower() and "difference" not in content.lower():
            issues.append("The response does not clearly compare the options")
            fix_instructions.append("Add an explicit comparison of the options or approaches.")

        if "conclusion" not in content.lower() and "summary" not in content.lower() and "recommend" not in content.lower():
            issues.append("The response does not include a clear conclusion")
            fix_instructions.append("Add a short conclusion or recommendation at the end.")

        status = "pass" if not issues else "revise"
        if status == "pass":
            issues = []
            fix_instructions = []

        LOGGER.info("ResearchCritic status: %s", status)
        LOGGER.info("ResearchCritic found %s issue(s)", len(issues))
        LOGGER.info("ResearchCritic prepared %s fix instruction(s)", len(fix_instructions))
        return {
            "status": status,
            "issues": issues,
            "fix_instructions": fix_instructions,
        }


class Contrarian(Agent):
    """Challenge the current result from a skeptical perspective."""

    name = "contrarian"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return objections and optional fixes if the result looks weak."""
        build = state.get("build") or {}
        content = str(build.get("content", "")).strip()
        issues: list[str] = []
        fix_instructions: list[str] = []
        objections: list[str] = []

        if not content:
            issues.append("There is no result to challenge")
            fix_instructions.append("Create a result before asking for contrarian review.")
        else:
            objections.append("What is the main tradeoff or downside of this result?")
            if len(content.split()) < 8:
                issues.append("The result is too thin to defend against criticism")
                fix_instructions.append("Add one tradeoff, risk, or alternative viewpoint.")

        status = "pass" if not issues else "revise"
        if status == "pass":
            issues = []
            fix_instructions = []

        return {
            "status": status,
            "issues": issues,
            "fix_instructions": fix_instructions,
            "objections": objections,
        }


class Debugger(Agent):
    """Turn critique feedback into concrete debugging guidance."""

    name = "debugger"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return targeted debugging notes when the current step needs revision."""
        critique = state.get("critique") or {}
        testing = state.get("testing") or {}
        issues = list(critique.get("issues", []))
        fix_instructions = list(critique.get("fix_instructions", []))
        debug_notes: list[str] = []

        if not issues:
            return {
                "status": "idle",
                "issues": [],
                "fix_instructions": [],
                "debug_notes": ["No debugging needed for this attempt."],
            }

        debug_notes.extend(f"Investigate: {issue}" for issue in issues)

        stdout = str(testing.get("stdout", "")).strip()
        stderr = str(testing.get("stderr", "")).strip()
        if stdout:
            snippet = stdout[-400:]
            debug_notes.append(f"Recent test output: {snippet}")
        if stderr:
            snippet = stderr[-400:]
            debug_notes.append(f"Recent test error output: {snippet}")
        if testing.get("command"):
            debug_notes.append(f"Re-run tests with: {' '.join(testing['command'])}")
        if any("Project tests failed" == issue for issue in issues):
            fix_instructions.append("Use the unittest output to identify the failing test and correct the code path it covers.")

        if not fix_instructions:
            fix_instructions = ["Review the failing step and apply a direct correction."]

        return {
            "status": "active",
            "issues": issues,
            "fix_instructions": fix_instructions,
            "debug_notes": debug_notes,
        }


class Analyzer(Agent):
    """Summarize the latest attempt and suggest the next action."""

    name = "analyzer"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return a short summary of the current state of work."""
        critique = state.get("critique") or {}
        build = state.get("build") or {}
        routing = state.get("routing") or {}
        research = state.get("research") or {}
        artifacts = state.get("artifacts") or {}
        status = critique.get("status", "unknown")
        next_action = "continue" if status == "revise" else "step_complete"
        fix_instructions = list(critique.get("fix_instructions", []))
        task_type = routing.get("task_type", "general_task")

        if status == "revise" and fix_instructions:
            recommended_next_step = fix_instructions[0]
            reason = "The latest review found a concrete fix to apply next."
        elif task_type == "research_task" and not research.get("findings") and not extract_urls(str(state.get("task", ""))):
            recommended_next_step = "Add one or more URLs to the task if you want live research sources."
            reason = "Research tasks can use stronger evidence when you include source URLs."
        elif task_type == "file_task" and build.get("path"):
            recommended_next_step = f"Review the generated file at {build['path']} and decide whether to keep or refine it."
            reason = "The file step is complete, so the next useful move is to inspect the created artifact."
        elif artifacts.get("items"):
            latest = artifacts["items"][-1]
            recommended_next_step = "Use the latest artifact as input for the next related subtask."
            reason = f"The session already produced an artifact that can help the next step: {latest.get('path') or 'in-memory result'}."
        else:
            recommended_next_step = "Move on to the next task or refine the current result if you want a tighter output."
            reason = "The current step is in a usable state."

        return {
            "summary": f"Current step status: {status}",
            "next_action": next_action,
            "recommended_next_step": recommended_next_step,
            "reason": reason,
        }


class ResearchAgent(Agent):
    """Fetch and summarize content from URLs found in the task."""

    name = "research_agent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Fetch URL content and return a small set of extracted findings."""
        urls = list(state.get("research_urls") or extract_urls(get_active_task(state)))
        if not urls:
            return {
                "status": "skipped",
                "notes": "No research URLs were provided in the task.",
                "sources": [],
                "findings": [],
            }

        findings: list[dict[str, str]] = []
        source_statuses: list[dict[str, str]] = []

        for url in urls[:3]:
            LOGGER.info("ResearchAgent fetching: %s", url)
            try:
                excerpt = self._fetch_text_excerpt(url)
                findings.append({"url": url, "excerpt": excerpt})
                source_statuses.append({"url": url, "status": "fetched"})
            except RuntimeError as exc:
                source_statuses.append({"url": url, "status": f"error: {exc}"})

        status = "completed" if findings else "error"
        notes = "Fetched live research sources." if findings else "Could not fetch any research sources."
        return {
            "status": status,
            "notes": notes,
            "sources": source_statuses,
            "findings": findings,
        }

    def _fetch_text_excerpt(self, url: str) -> str:
        """Fetch a page and return a short text excerpt."""
        request = Request(url, headers={"User-Agent": "multi-agent-core/0.1"})
        try:
            with urlopen(request, timeout=10) as response:
                raw_html = response.read().decode("utf-8", errors="ignore")
        except URLError as exc:
            raise RuntimeError(f"Failed to fetch {url}") from exc

        parser = _TextExtractor()
        parser.feed(raw_html)
        text = parser.get_text()
        if not text:
            raise RuntimeError(f"No readable text found at {url}")
        return text[:400]
