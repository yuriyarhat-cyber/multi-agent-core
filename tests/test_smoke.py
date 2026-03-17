"""Smoke tests for the minimal multi-agent flow."""

from __future__ import annotations

import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import (
    Builder,
    Critic,
    Orchestrator,
    Planner,
    ResearchCritic,
    Router,
    codex_llm,
    create_state,
    run_task,
)


class FakeResponsesClient:
    def create(self, model: str, input: str) -> SimpleNamespace:
        if "Target file:" in input:
            return SimpleNamespace(output_text="print('hello from generated file')\n")
        return SimpleNamespace(output_text=f"fake-response for {model}: {input[:20]}")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponsesClient()


class SmokeTest(unittest.TestCase):
    def test_public_api_imports_are_available(self) -> None:
        self.assertEqual(Orchestrator.__name__, "Orchestrator")
        self.assertEqual(Router.__name__, "Router")
        self.assertEqual(Planner.__name__, "Planner")
        self.assertEqual(Builder.__name__, "Builder")
        self.assertEqual(Critic.__name__, "Critic")
        self.assertEqual(ResearchCritic.__name__, "ResearchCritic")
        self.assertTrue(callable(create_state))
        self.assertTrue(callable(codex_llm))
        self.assertTrue(callable(run_task))

    def test_package_imports_as_library(self) -> None:
        command = [
            sys.executable,
            "-c",
            "import multi_agent_core; print(multi_agent_core.Orchestrator.__name__)",
        ]
        env = dict(**__import__("os").environ)
        env["PYTHONPATH"] = str(SRC)
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.stdout.strip(), "Orchestrator")

    def test_router_classifies_file_task(self) -> None:
        routing = Router().route("create file generated/hello.py")
        self.assertEqual(routing["task_type"], "file_task")
        self.assertEqual(routing["suggested_flow"], ["planner", "builder", "critic"])

    def test_router_classifies_text_task(self) -> None:
        routing = Router().route("rewrite this email into a short summary")
        self.assertEqual(routing["task_type"], "text_task")
        self.assertEqual(routing["suggested_flow"], ["planner", "builder", "critic"])

    def test_router_classifies_research_task(self) -> None:
        routing = Router().route("analyze and compare two onboarding approaches")
        self.assertEqual(routing["task_type"], "research_task")
        self.assertEqual(routing["suggested_flow"], ["planner", "builder", "critic", "research_critic"])

    def test_router_classifies_general_task(self) -> None:
        routing = Router().route("help me think through this task")
        self.assertEqual(routing["task_type"], "general_task")
        self.assertEqual(routing["suggested_flow"], ["planner", "builder", "critic"])

    @patch.dict("os.environ", {}, clear=True)
    def test_llm_raises_without_api_key(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY not set"):
            codex_llm("hello")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_llm_returns_text_with_stubbed_openai(self, mock_openai: object) -> None:
        result = codex_llm("hello world")
        self.assertIn("fake-response for test-model", result)
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_run_task_returns_basic_result_shape(self, mock_openai: object) -> None:
        result = run_task("Help me think through the next step", project_root=str(ROOT))

        self.assertEqual(result["task"], "Help me think through the next step")
        self.assertIn("routing", result)
        self.assertIn("plan", result)
        self.assertIn("history", result)
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_orchestrator_runs_full_flow(self, mock_openai: object) -> None:
        task = "Help me think through the next step"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        self.assertEqual(result["task"], task)
        self.assertEqual(result["routing"]["task_type"], "general_task")
        self.assertEqual(result["executed_flow"], ["planner", "builder", "critic"])
        self.assertEqual(result["plan"]["type"], "general_task")
        self.assertIn("steps", result["plan"])
        self.assertGreaterEqual(len(result["plan"]["steps"]), 1)
        self.assertIn("id", result["plan"]["steps"][0])
        self.assertIn("kind", result["plan"]["steps"][0])
        self.assertIn("description", result["plan"]["steps"][0])
        self.assertIn("status", result["critique"])
        self.assertIn(result["critique"]["status"], {"pass", "revise"})
        self.assertIn("issues", result["critique"])
        self.assertIn("fix_instructions", result["critique"])
        self.assertGreaterEqual(len(result["history"]), len(result["plan"]["steps"]))

        first_entry = result["history"][0]
        self.assertIn("agent", first_entry)
        self.assertIn("step", first_entry)
        self.assertIn("attempt", first_entry)
        self.assertIn("result", first_entry)
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_critic_returns_fix_instructions_and_builder_uses_them(self, mock_openai: object) -> None:
        task = "Prepare a short customer onboarding outline"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        first_step = result["plan"]["steps"][0]
        first_critique = next(
            entry["result"]
            for entry in result["history"]
            if entry["agent"] == "critic" and entry["attempt"] == 1 and entry["step"] == first_step
        )
        second_build = next(
            entry["result"]
            for entry in result["history"]
            if entry["agent"] == "builder" and entry["attempt"] == 2 and entry["step"] == first_step
        )

        self.assertEqual(first_critique["status"], "revise")
        self.assertGreaterEqual(len(first_critique["issues"]), 1)
        self.assertGreaterEqual(len(first_critique["fix_instructions"]), 1)
        self.assertTrue(second_build["used_feedback"])
        self.assertEqual(
            second_build["applied_fix_instructions"],
            first_critique["fix_instructions"],
        )
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_builder_creates_file_for_file_task(self, mock_openai: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task = "create file generated/hello.py"
            state = create_state(task)
            state["project_root"] = temp_dir

            result = Orchestrator().run(task=task, state=state)

            created_path = Path(temp_dir) / "generated" / "hello.py"
            self.assertTrue(created_path.exists())
            self.assertEqual(result["routing"]["task_type"], "file_task")
            self.assertEqual(result["executed_flow"], ["planner", "builder", "critic"])
            self.assertEqual(result["plan"]["type"], "file_task")
            self.assertEqual(result["plan"]["target_file"], "generated/hello.py")
            self.assertEqual(result["plan"]["file_action"], "write_file")
            self.assertEqual(
                [step["id"] for step in result["plan"]["steps"]],
                [
                    "identify_target_file",
                    "confirm_file_action",
                    "prepare_file_content",
                    "save_file_changes",
                    "verify_file_result",
                ],
            )
            self.assertEqual(result["build"]["action"], "write_file")
            self.assertEqual(result["build"]["path"], str(created_path.resolve()))
            self.assertIn("hello from generated file", created_path.read_text(encoding="utf-8"))
            self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_research_task_uses_double_critic_pass(self, mock_openai: object) -> None:
        task = "analyze and compare two onboarding approaches"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        self.assertEqual(result["routing"]["task_type"], "research_task")
        self.assertEqual(result["executed_flow"], ["planner", "builder", "critic", "research_critic"])
        first_step = result["plan"]["steps"][0]

        critic_entries = [
            entry for entry in result["history"]
            if entry["agent"] == "critic" and entry["attempt"] == 1 and entry["step"] == first_step
        ]
        research_critic_entries = [
            entry for entry in result["history"]
            if entry["agent"] == "research_critic" and entry["attempt"] == 1 and entry["step"] == first_step
        ]
        self.assertEqual(len(critic_entries), 1)
        self.assertEqual(len(research_critic_entries), 1)
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_general_task_does_not_use_research_critic(self, mock_openai: object) -> None:
        task = "Help me think through the next step"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        research_critic_entries = [
            entry for entry in result["history"]
            if entry["agent"] == "research_critic"
        ]
        self.assertEqual(result["executed_flow"], ["planner", "builder", "critic"])
        self.assertEqual(research_critic_entries, [])
        self.assertTrue(mock_openai.called)


if __name__ == "__main__":
    unittest.main()
