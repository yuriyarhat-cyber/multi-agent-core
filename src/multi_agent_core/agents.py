"""Simple agent implementations used by the orchestrator."""

from __future__ import annotations

from typing import Any

from .llm import codex_llm


class Agent:
    """Base class for all agents."""

    name = "agent"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Read the shared state and return this agent's structured result."""
        raise NotImplementedError("Agent subclasses must implement run().")


class Planner(Agent):
    """Break a task into a small list of reusable steps."""

    name = "planner"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a simple plan with a short summary and ordered steps."""
        task = str(state.get("task", "")).strip()
        summary = codex_llm(f"Plan task: {task}")
        words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]

        if not words:
            steps = ["Understand the task", "Produce a simple result", "Review the result"]
        else:
            focus = " ".join(words[:4])
            steps = [
                f"Understand the goal: {focus}",
                f"Create a first draft for: {focus}",
                f"Review and improve the draft for: {focus}",
            ]

        return {"steps": steps, "summary": summary}


class Builder(Agent):
    """Produce output for the current step."""

    name = "builder"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a draft output for the current step, using feedback if present."""
        step = state.get("current_step") or ""
        task = state.get("task") or ""
        previous_critique = state.get("critique") or {}
        issues = previous_critique.get("issues") or []
        feedback_note = ""
        if issues:
            feedback_note = f" Revised to address: {'; '.join(issues)}."

        prompt = f"Build step '{step}' for task '{task}'.{feedback_note}"
        content = (
            f"Step: {step}\n"
            f"Task: {task}\n"
            f"Draft: {codex_llm(prompt)}.{feedback_note}"
        ).strip()

        return {
            "step": step,
            "content": content,
            "used_feedback": bool(issues),
        }


class Critic(Agent):
    """Check the builder output and decide whether it passes."""

    name = "critic"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return pass or revise, plus a list of issues to fix."""
        build = state.get("build") or {}
        content = str(build.get("content", "")).strip()
        attempt = int(state.get("_attempt", 1))
        issues: list[str] = []

        if not content:
            issues.append("Builder returned empty content")

        if attempt == 1 and "Revised to address" not in content:
            issues.append("Add a revision note to show the feedback loop")

        status = "pass" if not issues else "revise"
        return {"status": status, "issues": issues}
