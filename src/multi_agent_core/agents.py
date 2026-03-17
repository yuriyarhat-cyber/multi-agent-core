"""Simple agent implementations used by the orchestrator."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .llm import codex_llm


LOGGER = logging.getLogger(__name__)


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
        """Create a stable structured plan for file or general tasks."""
        task = str(state.get("task", "")).strip()
        summary = codex_llm(f"Plan task: {task}")
        routing = state.get("routing") or {}
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
                    {
                        "id": "identify_target_file",
                        "kind": "analysis",
                        "description": f"Determine the target file: {target_file}",
                    },
                    {
                        "id": "confirm_file_action",
                        "kind": "analysis",
                        "description": f"Confirm the file action: {action}",
                    },
                    {
                        "id": "prepare_file_content",
                        "kind": "build",
                        "description": f"Prepare the content for {target_file}",
                    },
                    {
                        "id": "save_file_changes",
                        "kind": "write",
                        "description": f"Save the changes to {target_file}",
                    },
                    {
                        "id": "verify_file_result",
                        "kind": "review",
                        "description": f"Check the final result in {target_file}",
                    },
                ],
            }
        elif task_type == "text_task":
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the text task"
            plan = {
                "type": "text_task",
                "summary": summary,
                "steps": [
                    {
                        "id": "understand_text_goal",
                        "kind": "analysis",
                        "description": f"Understand the text goal: {focus}",
                    },
                    {
                        "id": "draft_text",
                        "kind": "build",
                        "description": f"Draft the text for: {focus}",
                    },
                    {
                        "id": "review_text",
                        "kind": "review",
                        "description": f"Review and tighten the text for: {focus}",
                    },
                ],
            }
        elif task_type == "research_task":
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the research task"
            plan = {
                "type": "research_task",
                "summary": summary,
                "steps": [
                    {
                        "id": "define_research_goal",
                        "kind": "analysis",
                        "description": f"Define what to analyze for: {focus}",
                    },
                    {
                        "id": "compare_findings",
                        "kind": "analysis",
                        "description": f"Compare the key points for: {focus}",
                    },
                    {
                        "id": "summarize_conclusion",
                        "kind": "review",
                        "description": f"Summarize the conclusion for: {focus}",
                    },
                    {
                        "id": "prepare_deeper_review",
                        "kind": "review",
                        "description": f"Prepare for a deeper research review of: {focus}",
                    },
                ],
            }
        else:
            words = [word.strip(".,:;!?") for word in task.split() if word.strip(".,:;!?")]
            focus = " ".join(words[:4]) if words else "the task"
            plan = {
                "type": "general_task",
                "summary": summary,
                "steps": [
                    {
                        "id": "understand_goal",
                        "kind": "analysis",
                        "description": f"Understand the goal: {focus}",
                    },
                    {
                        "id": "prepare_output",
                        "kind": "build",
                        "description": f"Prepare a first result for: {focus}",
                    },
                    {
                        "id": "review_result",
                        "kind": "review",
                        "description": f"Review the result for: {focus}",
                    },
                ],
            }

        LOGGER.info("Planner selected plan type: %s", plan["type"])
        LOGGER.info("Planner created %s step(s)", len(plan["steps"]))
        return plan


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
        task = state.get("task") or ""
        previous_critique = state.get("critique") or {}
        issues = previous_critique.get("issues") or []
        fix_instructions = previous_critique.get("fix_instructions") or []
        project_root = Path(state.get("project_root") or Path.cwd())
        feedback_note = ""
        if fix_instructions:
            feedback_note = f" Apply these fixes: {'; '.join(fix_instructions)}."
        elif issues:
            feedback_note = f" Revised to address: {'; '.join(issues)}."

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
                fix_instructions=list(fix_instructions),
            )

        step_description = self._step_description(step)
        prompt = f"Build step '{step_description}' for task '{task}'.{feedback_note}"
        content = (
            f"Step: {step_description}\n"
            f"Task: {task}\n"
            f"Draft: {codex_llm(prompt)}.{feedback_note}"
        ).strip()

        return {
            "step": step_description,
            "content": content,
            "used_feedback": bool(issues or fix_instructions),
            "applied_fix_instructions": list(fix_instructions),
        }

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
            f"Produce only the file content.{feedback_note}"
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


class Critic(Agent):
    """Check the builder output and decide whether it passes."""

    name = "critic"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return pass or revise, plus a list of issues to fix."""
        build = state.get("build") or {}
        content = str(build.get("content", "")).strip()
        attempt = int(state.get("_attempt", 1))
        review_pass = str(state.get("_critic_pass_label", "review"))
        issues: list[str] = []
        fix_instructions: list[str] = []

        if not content:
            issues.append("Builder returned empty content")
            fix_instructions.append("Generate non-empty output for the current step.")

        if attempt == 1 and "Apply these fixes:" not in content and "Revised to address:" not in content:
            issues.append("Add a revision note to show the feedback loop")
            fix_instructions.append("Add a short revision note that clearly reflects the critic feedback.")

        if review_pass == "second_review" and attempt == 1:
            issues.append("Add a deeper review note for the second critic pass")
            fix_instructions.append("Strengthen the result with a deeper second-review note before finalizing.")

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
        task = str(state.get("task", "")).lower()
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
