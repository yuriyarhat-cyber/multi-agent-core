"""Simple task router for choosing a task type before planning."""

from __future__ import annotations

import re


class Router:
    """Classify a task into a small set of stable task types."""

    def route(self, task: str) -> dict[str, object]:
        """Return task type, reason, and the suggested default flow."""
        task_lower = task.lower()

        file_keywords = ("file", "create", "write", "update", "append", "read", "path", "folder")
        text_keywords = ("text", "letter", "email", "summary", "outline", "rewrite")
        research_keywords = ("analyze", "compare", "research", "investigate")

        if self._has_keyword(task_lower, file_keywords):
            return {
                "task_type": "file_task",
                "reason": "The task mentions files or file operations.",
                "suggested_flow": ["planner", "builder", "critic"],
            }

        if self._has_keyword(task_lower, text_keywords):
            return {
                "task_type": "text_task",
                "reason": "The task is focused on producing or revising text.",
                "suggested_flow": ["planner", "builder", "critic"],
            }

        if self._has_keyword(task_lower, research_keywords):
            return {
                "task_type": "research_task",
                "reason": "The task asks for analysis, comparison, or investigation.",
                "suggested_flow": ["planner", "builder", "critic", "research_critic"],
            }

        return {
            "task_type": "general_task",
            "reason": "The task does not strongly match file, text, or research keywords.",
            "suggested_flow": ["planner", "builder", "critic"],
        }

    def _has_keyword(self, text: str, keywords: tuple[str, ...]) -> bool:
        """Check keywords by whole words to avoid accidental substring matches."""
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                return True
        return False
