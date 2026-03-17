"""Smoke tests for the minimal multi-agent flow."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import Orchestrator, codex_llm, create_state


class FakeResponsesClient:
    def create(self, model: str, input: str) -> SimpleNamespace:
        return SimpleNamespace(output_text=f"fake-response for {model}: {input[:20]}")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponsesClient()


class SmokeTest(unittest.TestCase):
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
    def test_orchestrator_runs_full_flow(self, mock_openai: object) -> None:
        task = "Prepare a short customer onboarding outline"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        self.assertEqual(result["task"], task)
        self.assertIn("steps", result["plan"])
        self.assertGreaterEqual(len(result["plan"]["steps"]), 1)
        self.assertIn("status", result["critique"])
        self.assertIn(result["critique"]["status"], {"pass", "revise"})
        self.assertGreaterEqual(len(result["history"]), len(result["plan"]["steps"]))

        first_entry = result["history"][0]
        self.assertIn("step", first_entry)
        self.assertIn("attempt", first_entry)
        self.assertIn("build", first_entry)
        self.assertIn("critique", first_entry)
        self.assertTrue(mock_openai.called)


if __name__ == "__main__":
    unittest.main()
